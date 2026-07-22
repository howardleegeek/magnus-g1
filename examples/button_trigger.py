"""Wireless-remote button → action daemon (showroom trigger).

Listens passively to rt/lowstate, decodes the remote's buttons, and fires the
actions mapped in routines/buttons.json:

    "RB": {"play": "voices/showroom_welcome.wav"}   stream a WAV to the speaker
    "A":  {"tts":  "Hello!"}                        robot's built-in TTS
    "Y":  {"cmd":  "some shell command"}            anything else

Production behaviors:
  - debounce: fires on press EDGE only, per-button cooldown (config)
  - audio busy-guard: a press while audio is playing is logged and ignored
  - hot-reload: edit/rsync buttons.json and it reloads within ~1 s, no restart
    (a broken new config is rejected and the old one keeps running)
  - heartbeat: warns if no controller data for 10 s (remote off / unpaired?)

Run on the robot's Jetson (via systemd, see deploy/magnus-buttons.service) or
from a laptop:  python examples/button_trigger.py <iface> [--debug]
"""

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

import voice
from button_engine import ButtonEngine, load_config, parse_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "routines" / "buttons.json"
HEARTBEAT_TIMEOUT = 10.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Player:
    """Owns the AudioClient; ensures one audio at a time (busy-guard)."""

    def __init__(self, audio_client, tts_speaker: int):
        self.client = audio_client
        self.speaker = tts_speaker
        self._thread = None

    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def play_wav(self, pcm: bytes, label: str) -> None:
        def run():
            try:
                voice.stream_wav(self.client, pcm)
                log(f"finished: {label}")
            except Exception as e:  # never let audio kill the daemon
                log(f"ERROR playing {label}: {e}")
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def tts(self, text: str) -> None:
        try:
            self.client.TtsMaker(text, self.speaker)
        except Exception as e:
            log(f"ERROR tts: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iface", help="network interface (eth0 on the Jetson)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--speaker", type=int, default=1, help="TTS voice: 1=EN, 0=CN")
    parser.add_argument("--debug", action="store_true", help="log every key change")
    args = parser.parse_args()

    cooldown, mapping = load_config(args.config, REPO_ROOT)
    # Preload audio so button presses never wait on disk (and bad WAVs fail at startup).
    pcm_cache = {b: voice.load_pcm(REPO_ROOT / a["play"])
                 for b, a in mapping.items() if "play" in a}
    config_mtime = args.config.stat().st_mtime

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    ChannelFactoryInitialize(0, args.iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()
    player = Player(audio, args.speaker)

    latest = {"remote": None, "t": 0.0}

    def on_lowstate(msg):  # DDS thread: keep it trivial, never raise
        try:
            latest["remote"] = bytes(msg.wireless_remote)
            latest["t"] = time.monotonic()
        except Exception:
            pass

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(on_lowstate, 10)

    engine = ButtonEngine(mapping, cooldown)
    log(f"ready — {len(mapping)} button(s) mapped, cooldown {cooldown}s, config {args.config}")
    warned_hb = False
    prev_keys: frozenset = frozenset()

    while True:
        time.sleep(0.05)
        now = time.monotonic()

        # hot-reload config (rejected configs keep the old mapping running)
        try:
            mtime = args.config.stat().st_mtime
            if mtime != config_mtime:
                config_mtime = mtime
                try:
                    cooldown, mapping = load_config(args.config, REPO_ROOT)
                    pcm_cache = {b: voice.load_pcm(REPO_ROOT / a["play"])
                                 for b, a in mapping.items() if "play" in a}
                    engine = ButtonEngine(mapping, cooldown)
                    log(f"config reloaded — {len(mapping)} button(s)")
                except SystemExit as e:
                    log(f"BAD CONFIG kept old mapping: {e}")
        except OSError:
            pass

        # heartbeat
        if latest["t"] and now - latest["t"] > HEARTBEAT_TIMEOUT:
            if not warned_hb:
                log(f"WARN: no controller data for {HEARTBEAT_TIMEOUT:.0f}s — remote off/unpaired?")
                warned_hb = True
            continue
        warned_hb = False

        keys = parse_keys(latest["remote"])
        if args.debug and keys != prev_keys:
            log(f"keys: {sorted(keys) or '—'}")
        prev_keys = keys

        for btn, action in engine.update(keys, now):
            if "play" in action:
                if player.busy():
                    log(f"{btn} pressed — ignored, audio still playing")
                else:
                    log(f"{btn} → play {action['play']}")
                    player.play_wav(pcm_cache[btn], action["play"])
            elif "tts" in action:
                if player.busy():
                    log(f"{btn} pressed — ignored, audio still playing")
                else:
                    log(f"{btn} → tts {action['tts']!r}")
                    player.tts(action["tts"])
            elif "cmd" in action:
                log(f"{btn} → cmd: {action['cmd']}")
                try:
                    # shell=True is intentional: buttons.json is the operator's
                    # scripting surface, editable only by users who already have
                    # an SSH shell on this machine — no privilege is added.
                    subprocess.Popen(action["cmd"], shell=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    log(f"ERROR cmd: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
        sys.exit(0)
