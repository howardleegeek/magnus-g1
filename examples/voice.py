"""Play voice on the G1 speaker: WAV files, built-in TTS, volume, stop.

Robot firmware accepts ONLY 16 kHz, mono, 16-bit PCM WAV. Make a compliant
file from any audio (TTS output, recording, mp3):

    ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 voices/hello.wav

Usage:
    python examples/voice.py --check voices/hello.wav       # offline validation, no robot/SDK
    python examples/voice.py <iface> --play voices/hello.wav
    python examples/voice.py <iface> --tts "Hello from Magnus Labs"
    python examples/voice.py <iface> --volume 85
    python examples/voice.py <iface> --stop                 # kill any playing audio
"""

import argparse
import sys
import time
import wave
from pathlib import Path

# Constants mirror the official g1 audio example (wav.py): 96000 bytes ≈ 3 s
# of 16 kHz 16-bit mono; 1 s pause between chunk sends.
CHUNK = 96000
CHUNK_SLEEP = 1.0
BYTES_PER_SEC = 32000  # 16000 Hz * 2 bytes
APP = "magnus"


def load_pcm(path) -> bytes:
    """Validate 16 kHz/mono/16-bit and return raw PCM bytes. SystemExit if not."""
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as w:
            rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            if (rate, ch, width) != (16000, 1, 2):
                sys.exit(
                    f"{path}: needs 16000 Hz mono 16-bit, got {rate} Hz / {ch} ch / {8*width}-bit\n"
                    f"fix:  ffmpeg -i {path} -ar 16000 -ac 1 -sample_fmt s16 {path.stem}_fixed.wav")
            return w.readframes(w.getnframes())
    except (OSError, EOFError, wave.Error) as e:
        sys.exit(f"cannot read {path}: {e}")


def stream_wav(client, pcm: bytes) -> None:
    """Send PCM in official-example cadence, wait for tail, then stop the stream."""
    stream_id = str(int(time.time() * 1000))
    for off in range(0, len(pcm), CHUNK):
        client.PlayStream(APP, stream_id, pcm[off:off + CHUNK])
        time.sleep(CHUNK_SLEEP)
    # chunks were paced 1 s apart but each holds ~3 s of audio — wait out the rest
    remainder = len(pcm) / BYTES_PER_SEC - (len(pcm) // CHUNK + 1) * CHUNK_SLEEP
    time.sleep(max(0.5, remainder))
    client.PlayStop(APP)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iface", nargs="?", help="network interface, e.g. eth0 / en7")
    parser.add_argument("--check", type=Path, help="validate a WAV offline and exit")
    parser.add_argument("--play", type=Path, help="stream a WAV to the robot speaker")
    parser.add_argument("--tts", help="speak text via the robot's built-in TTS")
    parser.add_argument("--speaker", type=int, default=0, help="TTS speaker id (default 0)")
    parser.add_argument("--volume", type=int, help="set speaker volume 0-100")
    parser.add_argument("--stop", action="store_true", help="stop any playing audio")
    args = parser.parse_args()

    if args.check:
        pcm = load_pcm(args.check)
        print(f"OK: {args.check} — {len(pcm) / BYTES_PER_SEC:.1f}s, "
              f"{'1 chunk (routine-safe)' if len(pcm) <= CHUNK else f'{len(pcm) // CHUNK + 1} chunks (standalone play only)'}")
        return
    if not args.iface:
        parser.error("network interface required (or use --check for offline validation)")
    if not (args.play or args.tts or args.volume is not None or args.stop):
        parser.error("nothing to do: pass --play/--tts/--volume/--stop")

    pcm = load_pcm(args.play) if args.play else None  # validate before touching robot

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    ChannelFactoryInitialize(0, args.iface)
    client = AudioClient()
    client.SetTimeout(10.0)
    client.Init()

    if args.volume is not None:
        client.SetVolume(args.volume)
        print(f"volume set to {args.volume}")
    if args.stop:
        client.PlayStop(APP)
        print("stopped")
    if args.tts:
        client.TtsMaker(args.tts, args.speaker)
        print(f"tts: {args.tts!r}")
    if pcm is not None:
        print(f"playing {args.play} ({len(pcm) / BYTES_PER_SEC:.1f}s)")
        stream_wav(client, pcm)
        print("done")


if __name__ == "__main__":
    main()
