"""Resident voice chat: mic AUDIO → gemini-2.5-flash (hears it directly) → robot speaks.

Why this beats the old design: vosk's small model garbled speech, so a smart LLM
still got nonsense and answered badly. Here vosk is used ONLY as a voice-activity
detector (did the person stop talking?); the actual UNDERSTANDING is done by
sending the utterance's raw audio to gemini-2.5-flash, which transcribes AND
answers accurately in one call. Falls back to text models (via the vosk guess)
only if the audio call fails.

Run:  set -a; . ./openrouter.env; set +a; venv/bin/python chat_daemon.py eth0
Env: OPENROUTER_API_KEY, MINIMAX_API_KEY, MIC_SOURCE, TTS_SPEAKER, plus the
XDG_RUNTIME_DIR/PULSE_SERVER needed for parec.
"""

import base64
import fcntl
import io
import json
import os
import subprocess
import sys
import time
import wave
import urllib.request
import urllib.error

AUDIO_MODEL = os.environ.get("AUDIO_MODEL", "google/gemini-2.5-flash")
TEXT_MODELS = ["google/gemini-2.5-flash", "openai/gpt-4o-mini"]  # fallback path
VOSK_MODEL = os.environ.get("VOSK_MODEL", "/home/unitree/magnus/vosk-model")
MIC_SOURCE = os.environ.get(
    "MIC_SOURCE",
    "alsa_input.usb-DCMT_Technology_USB_Lavalier_Microphone_214b206000000178-00.mono-fallback",
)
TTS_SPEAKER = int(os.environ.get("TTS_SPEAKER", "1"))
API_URL = "https://openrouter.ai/api/v1/chat/completions"
RATE = 16000
MIN_WORDS = 2  # vosk VAD gate: fewer "words" than this = ignore as noise

SYSTEM_PROMPT = (
    "You are the friendly voice assistant at the showroom booth. Answer the "
    "visitor's spoken question in ONE short spoken sentence of AT MOST 12 words — "
    "punchy and conversational, never a list. Use the "
    "Showroom facts below; do NOT invent details you weren't given (exact price, "
    "stock, delivery, hours) — offer to get a showroom team member instead. "
    "Always answer in English."
)


CONTEXT_PATH = os.environ.get(
    "SHOWROOM_CONTEXT", "/home/unitree/magnus/magnus-g1/routines/showroom_context.md")


def system_prompt():
    """Base persona + the editable showroom knowledge file (re-read each turn,
    so staff can update facts without restarting)."""
    try:
        facts = open(CONTEXT_PATH).read().strip()
        return SYSTEM_PROMPT + "\n\nShowroom facts (answer from these; do not contradict them):\n" + facts
    except Exception:
        return SYSTEM_PROMPT


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _post(body):
    key = os.environ["OPENROUTER_API_KEY"]
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        resp = json.loads(r.read())
    m = resp["choices"][0]["message"]
    return (m.get("content") or m.get("reasoning") or "").strip()


# the RB welcome clip's words — if the mic "hears" this, it's our own mp3 playing,
# not a visitor. Skip it so the LLM never talks over / repeats the welcome.
WELCOME_WORDS = set(
    "welcome to the showroom located in building b 7th seventh "
    "floor enjoy exploring our new outdoor collection".split())


def is_welcome_echo(guess: str) -> bool:
    w = set(guess.lower().split())
    return bool(w) and len(w & WELCOME_WORDS) / len(w) > 0.5


def transcribe_audio(pcm: bytes) -> str:
    """Accurate ears: gemini transcribes the utterance (small, fast call)."""
    b64 = base64.b64encode(pcm_to_wav(pcm)).decode()
    return _post({"model": AUDIO_MODEL,
                  "messages": [{"role": "user", "content": [
                      {"type": "text", "text": "Transcribe this speech exactly, nothing else."},
                      {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}]}],
                  "max_tokens": 60, "temperature": 0})


def answer(pcm: bytes, vosk_guess: str, history) -> str:
    """Ears = gemini transcription; brain = MiniMax (paid quota). Fallback = gemini."""
    heard = vosk_guess
    try:
        t = time.time()
        heard = transcribe_audio(pcm) or vosk_guess
        log(f"[transcribed {time.time()-t:.1f}s: {heard!r}]")
    except Exception as e:
        log(f"transcribe failed ({e}); using vosk guess")
    msgs = [{"role": "system", "content": system_prompt()}] + history[-4:] + [
        {"role": "user", "content": heard or "(unclear)"}]
    text = ask_minimax(msgs)                       # primary brain: MiniMax
    if text:
        return text
    for model in TEXT_MODELS:                      # fallback: gemini/gpt text
        try:
            text = _post({"model": model, "messages": msgs,
                          "max_tokens": 50, "temperature": 0.5})
            if text:
                log(f"[text via {model}]")
                return text
        except Exception:
            continue
    return ""


def ask_minimax(msgs):
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        return ""
    body = {"model": "MiniMax-M2", "messages": msgs, "max_tokens": 120, "temperature": 0.6}
    req = urllib.request.Request(
        "https://api.minimax.io/v1/text/chatcompletion_v2",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        if resp.get("base_resp", {}).get("status_code") == 0:
            log("[minimax fallback]")
            m = resp["choices"][0]["message"]
            return (m.get("content") or m.get("reasoning_content") or "").strip()
    except Exception as e:
        log(f"minimax -> {e}")
    return ""


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: chat_daemon.py <iface>")
    iface = sys.argv[1]

    from vosk import Model, KaldiRecognizer
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    log("loading vosk (VAD only)...")
    rec = KaldiRecognizer(Model(VOSK_MODEL), RATE)

    ChannelFactoryInitialize(0, iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()

    parec = subprocess.Popen(
        ["parec", f"--device={MIC_SOURCE}", f"--rate={RATE}", "--channels=1",
         "--format=s16le"], stdout=subprocess.PIPE)

    def drain_mic():
        fd = parec.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            while parec.stdout.read(65536):
                pass
        except Exception:
            pass
        finally:
            fcntl.fcntl(fd, fcntl.F_SETFL, fl)

    history = []
    utter = bytearray()
    log("READY — just talk. (Ctrl-C to stop)")
    try:
        while True:
            data = parec.stdout.read(4000)
            if not data:
                break
            utter += data
            if not rec.AcceptWaveform(data):
                continue
            guess = json.loads(rec.Result()).get("text", "").strip()
            if len(guess.split()) < MIN_WORDS:   # not enough speech → drop as noise
                utter = bytearray()
                continue
            pcm = bytes(utter)
            utter = bytearray()
            if is_welcome_echo(guess):
                log(f"(ignored welcome mp3 playing: {guess!r})")
                rec.Reset()
                continue
            log(f"heard(~{len(pcm)//RATE//2}s, vosk guess: {guess!r})")
            reply = answer(pcm, guess, history) or "Sorry, could you say that again?"
            log(f"reply: {reply}")
            history += [{"role": "user", "content": guess},
                        {"role": "assistant", "content": reply}]
            # speak; suppress self-hearing the whole time, then drain the tail
            audio.TtsMaker(reply, TTS_SPEAKER)
            # mute only for roughly how long the speech actually takes (~14 chars/s),
            # then drain the tail. Keeps latency low without hearing ourselves.
            until = time.monotonic() + max(1.5, len(reply) * 0.075)
            while time.monotonic() < until:
                parec.stdout.read(8000)
            drain_mic()
            rec.Reset()
            utter = bytearray()
    except KeyboardInterrupt:
        pass
    finally:
        parec.terminate()
        log("bye")


if __name__ == "__main__":
    main()
