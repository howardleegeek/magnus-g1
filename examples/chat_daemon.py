"""Resident low-latency voice chat: listen continuously → GPT → robot speaks.

Unlike chat_assistant.py (one-shot, fixed 5s record, reloads everything each
call), this stays resident: the vosk model and AudioClient load ONCE, and it
listens with vosk endpoint detection — it reacts the moment you stop talking,
no fixed wait. Latency drops from ~15s to ~3-4s per turn.

  parec (continuous PCM) → vosk streaming (endpoint = you stopped) →
  free fast LLM → robot TTS. While the robot speaks, mic input is discarded so
  it never hears itself.

Run:  set -a; . ./openrouter.env; set +a; venv/bin/python chat_daemon.py eth0
Env: OPENROUTER_API_KEY, MIC_SOURCE, OR_MODEL, VOSK_MODEL, TTS_SPEAKER.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# try these in order — if one is rate-limited (429/busy), fall through to the next
MODELS = os.environ.get("OR_MODEL", "google/gemma-4-26b-a4b-it:free").split(",") + [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-20b:free",
]
VOSK_MODEL = os.environ.get("VOSK_MODEL", "/home/unitree/magnus/vosk-model")
MIC_SOURCE = os.environ.get(
    "MIC_SOURCE",
    "alsa_input.usb-Anker_PowerConf_C200_Anker_PowerConf_C200_ACNV9P1D30466073-02.analog-stereo",
)
TTS_SPEAKER = int(os.environ.get("TTS_SPEAKER", "1"))
API_URL = "https://openrouter.ai/api/v1/chat/completions"
RATE = 16000
MIN_WORDS = 2  # ignore stray 1-word noise

SYSTEM_PROMPT = (
    "You are a friendly voice assistant for the showroom (the booth, "
    "Building B, 7th floor). Answer about sofas, the outdoor collection, layout, "
    "and hours. Reply in ENGLISH, ONE short spoken sentence, no lists/markdown."
)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def ask_gpt(question, history):
    key = os.environ["OPENROUTER_API_KEY"]
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-4:] + [
        {"role": "user", "content": question}]
    for model in MODELS:  # fall through to the next model if one is rate-limited
        body = {"model": model.strip(), "messages": msgs,
                "max_tokens": 120, "temperature": 0.7}
        req = urllib.request.Request(
            API_URL, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            msg = resp["choices"][0]["message"]
            text = (msg.get("content") or msg.get("reasoning") or "").strip()
            if text:
                return text
        except urllib.error.HTTPError as e:
            log(f"{model.strip()} -> {e.code}, trying next model")
            continue
        except Exception as e:
            log(f"{model.strip()} -> {e}, trying next model")
            continue
    return ""


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: chat_daemon.py <iface>")
    iface = sys.argv[1]

    from vosk import Model, KaldiRecognizer
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    log("loading vosk model (once)...")
    rec = KaldiRecognizer(Model(VOSK_MODEL), RATE)

    ChannelFactoryInitialize(0, iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()

    history = []
    parec = subprocess.Popen(
        ["parec", f"--device={MIC_SOURCE}", f"--rate={RATE}", "--channels=1",
         "--format=s16le"], stdout=subprocess.PIPE)
    log("READY — just talk. (Ctrl-C to stop)")

    try:
        while True:
            data = parec.stdout.read(4000)
            if not data:
                break
            if not rec.AcceptWaveform(data):
                continue
            text = json.loads(rec.Result()).get("text", "").strip()
            if len(text.split()) < MIN_WORDS:
                continue
            log(f"heard: {text!r}")
            reply = ask_gpt(text, history) or "Sorry, could you repeat that?"
            log(f"reply: {reply}")
            history += [{"role": "user", "content": text},
                        {"role": "assistant", "content": reply}]
            # speak, and discard everything the mic hears meanwhile (don't self-listen)
            audio.TtsMaker(reply, TTS_SPEAKER)
            speak_until = time.monotonic() + max(2.0, len(reply) * 0.08)
            while time.monotonic() < speak_until:
                parec.stdout.read(4000)
            rec.Reset()  # clear buffered audio before listening again
    except KeyboardInterrupt:
        pass
    finally:
        parec.terminate()
        log("bye")


if __name__ == "__main__":
    main()
