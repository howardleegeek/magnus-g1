"""Voice assistant: press-to-talk → local Whisper (ASR) → OpenRouter GPT → robot speaks.

Fully free pipeline (on the robot, needs internet + USB mic + OPENROUTER_API_KEY):
  1. record ~5s from the USB mic (parecord)
  2. transcribe locally with faster-whisper (offline, free)
  3. send the text to a FREE OpenRouter text model (openai/gpt-oss) with a
     showroom-assistant system prompt
  4. speak the reply via the robot's built-in TTS (AudioClient)

Wire it to a button in routines/buttons.json:
  "A": { "cmd": "bash -lc 'cd /home/unitree/magnus && set -a; . ./openrouter.env; set +a; venv/bin/python magnus-g1/examples/chat_assistant.py eth0'" }

Env: OPENROUTER_API_KEY. Config: MIC_SOURCE, REC_SECS, OR_MODEL, WHISPER_SIZE, TTS_SPEAKER.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

MODEL = os.environ.get("OR_MODEL", "openai/gpt-oss-20b:free")
VOSK_MODEL = os.environ.get("VOSK_MODEL", "/home/unitree/magnus/vosk-model")
MIC_SOURCE = os.environ.get(
    "MIC_SOURCE",
    "alsa_input.usb-Anker_PowerConf_C200_Anker_PowerConf_C200_ACNV9P1D30466073-02.analog-stereo",
)
REC_SECS = float(os.environ.get("REC_SECS", "5"))
TTS_SPEAKER = int(os.environ.get("TTS_SPEAKER", "1"))  # 1=English
REC_PATH = "/tmp/chat_q.wav"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a friendly voice assistant for the showroom (the booth, "
    "Building B, 7th floor). Answer visitors' questions about sofas, the outdoor "
    "collection, store layout, and hours. Reply in ENGLISH, SHORT — 1 to 2 "
    "spoken sentences, no lists, no markdown."
)

# cache the vosk model across calls if the process is reused
_VMODEL = None


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def record() -> str:
    log(f"recording {REC_SECS}s from mic...")
    subprocess.run(
        ["timeout", str(REC_SECS + 1), "parecord", f"--device={MIC_SOURCE}",
         "--rate=16000", "--channels=1", "--format=s16le", "--file-format=wav", REC_PATH],
        check=False,
    )
    log(f"recorded {Path(REC_PATH).stat().st_size} bytes")
    return REC_PATH


def transcribe(wav_path: str) -> str:
    global _VMODEL
    import wave
    from vosk import Model, KaldiRecognizer

    if _VMODEL is None:
        log("loading vosk model...")
        _VMODEL = Model(VOSK_MODEL)
    wf = wave.open(wav_path, "rb")
    rec = KaldiRecognizer(_VMODEL, wf.getframerate())
    parts = []
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            parts.append(json.loads(rec.Result()).get("text", ""))
    parts.append(json.loads(rec.FinalResult()).get("text", ""))
    text = " ".join(p for p in parts if p).strip()
    log(f"heard: {text!r}")
    return text


def ask_gpt(question: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set (source ~/magnus/openrouter.env)")
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question or "(the visitor said something unclear)"},
        ],
        "max_tokens": 200,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    log(f"asking GPT ({MODEL})...")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"OpenRouter error {e.code}: {e.read().decode()[:200]}")
    msg = resp["choices"][0]["message"]
    text = (msg.get("content") or msg.get("reasoning") or "").strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        text = "Sorry, I didn't catch that. Could you say it again?"
    log(f"reply: {text}")
    return text


def speak(iface: str, text: str) -> None:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    ChannelFactoryInitialize(0, iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()
    audio.TtsMaker(text, TTS_SPEAKER)
    time.sleep(max(2.0, len(text) * 0.09))


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: chat_assistant.py <iface>  (e.g. eth0)")
    iface = sys.argv[1]
    try:
        wav = record()
        question = transcribe(wav)
        reply = ask_gpt(question)
        speak(iface, reply)
        log("done")
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
