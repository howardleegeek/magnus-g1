"""Wireless-remote button → action daemon (showroom trigger).

Listens passively to rt/lowstate, decodes the remote's buttons, and fires the
actions mapped in routines/buttons.json:

    "RB": {"play": "voices/showroom_welcome.wav"}   stream a WAV to the speaker
    "A":  {"tts":  "Hello!"}                        robot's built-in TTS
    "Y":  {"cmd":  "some shell command"}            anything else

Production behaviors:
  - debounce: press EDGE only + per-button cooldown + solo-grace window (a
    button that is part of a two-key system combo never fires)
  - audio busy-guard covers BOTH WAV streaming and TTS (estimated duration);
    audio work runs off-thread so button sampling never stalls
  - volume asserted at startup and on config change ("volume" key) — survives
    the Jetson's documented random reboots via systemd Restart
  - hot-reload: edit/rsync buttons.json → reload within ~1 s, no restart; ANY
    bad config (including type errors) is rejected and the old one keeps running
  - startup priming: a button physically held while the service starts does
    not fire
  - lowstate watchdog: warns every 5 s until the FIRST message arrives (wrong
    iface / DDS / robot off), then warns if the stream stops. Note: a powered-
    off remote is NOT detectable from lowstate — that check is physical.

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
DEFAULT_VOLUME = 85
TTS_SEC_PER_CHAR = 0.09  # crude speech-duration estimate for busy-guard
TTS_MIN_SEC = 2.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Player:
    """Owns the AudioClient; enforces one audio at a time across WAV and TTS."""

    def __init__(self, audio_client, tts_speaker: int):
        self.client = audio_client
        self.speaker = tts_speaker
        self._thread: threading.Thread | None = None

    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _start(self, target, label: str) -> None:
        def run():
            try:
                target()
                log(f"finished: {label}")
            except Exception as e:  # audio failures must never kill the daemon
                log(f"ERROR audio ({label}): {e}")

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def play_wav(self, pcm: bytes, label: str) -> None:
        self._start(lambda: voice.stream_wav(self.client, pcm), label)

    def tts(self, text: str) -> None:
        # TtsMaker returns on RPC acceptance, not speech end (verified against
        # SDK source) — hold the busy slot for the estimated speech duration.
        hold = max(TTS_MIN_SEC, len(text) * TTS_SEC_PER_CHAR)

        def run():
            self.client.TtsMaker(text, self.speaker)
            time.sleep(hold)

        self._start(run, f"tts {text[:40]!r}")

    def set_volume(self, vol: int) -> None:
        try:
            self.client.SetVolume(int(vol))
            log(f"volume set to {int(vol)}")
        except Exception as e:
            log(f"ERROR SetVolume: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "iface", help="network interface (eth0/eth1 on the Jetson — `ip a`)"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--speaker", type=int, default=1, help="TTS voice: 1=EN, 0=CN")
    parser.add_argument("--debug", action="store_true", help="log every key change")
    args = parser.parse_args()

    cfg = load_config(args.config, REPO_ROOT)
    # Preload audio so presses never wait on disk (and bad WAVs fail at startup).
    pcm_cache = {
        b: voice.load_pcm(REPO_ROOT / a["play"])
        for b, a in cfg.mapping.items()
        if "play" in a
    }
    config_mtime = args.config.stat().st_mtime

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

    ChannelFactoryInitialize(0, args.iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()
    player = Player(audio, args.speaker)

    try:  # GetVolume doubles as an audio-service/firmware probe
        log(f"audio service probe: GetVolume -> {audio.GetVolume()}")
    except Exception as e:
        log(
            f"WARN: GetVolume failed ({e}) — check Vui_Service version if audio is dead"
        )
    player.set_volume(cfg.volume if cfg.volume is not None else DEFAULT_VOLUME)

    latest = {"remote": None, "t": 0.0}

    def on_lowstate(msg):  # DDS thread: keep it trivial, never raise
        try:
            latest["remote"] = bytes(msg.wireless_remote)
            latest["t"] = time.monotonic()
        except Exception:
            pass

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(on_lowstate, 10)

    engine = ButtonEngine(cfg.mapping, cfg.cooldown, cfg.grace)
    log(
        f"ready — {len(cfg.mapping)} button(s), cooldown {cfg.cooldown}s, "
        f"grace {cfg.grace}s, config {args.config}"
    )

    start_t = time.monotonic()
    got_first = False
    next_nodata_warn = start_t + 5.0
    warned_hb = False
    primed = False
    prev_keys: frozenset = frozenset()

    while True:
        time.sleep(0.05)
        now = time.monotonic()

        # hot-reload config (a rejected config keeps the old mapping running)
        try:
            mtime = args.config.stat().st_mtime
            if mtime != config_mtime:
                config_mtime = mtime
                try:
                    new_cfg = load_config(args.config, REPO_ROOT)
                    new_cache = {
                        b: voice.load_pcm(REPO_ROOT / a["play"])
                        for b, a in new_cfg.mapping.items()
                        if "play" in a
                    }
                    engine = ButtonEngine(
                        new_cfg.mapping, new_cfg.cooldown, new_cfg.grace
                    ).carry_from(engine)
                    pcm_cache = new_cache
                    if new_cfg.volume is not None and new_cfg.volume != cfg.volume:
                        player.set_volume(new_cfg.volume)
                    cfg = new_cfg
                    log(f"config reloaded — {len(cfg.mapping)} button(s)")
                except SystemExit as e:
                    log(f"BAD CONFIG kept old mapping: {e}")
                except Exception as e:
                    log(f"BAD CONFIG (unexpected) kept old mapping: {e}")
        except OSError:
            pass

        # lowstate watchdog: never-arrived vs stopped
        if latest["t"] == 0.0:
            if now >= next_nodata_warn:
                log(
                    f"WARN: no lowstate data after {now - start_t:.0f}s — "
                    f"check network interface ({args.iface}?), DDS, robot power"
                )
                next_nodata_warn = now + 5.0
            continue
        if not got_first:
            got_first = True
            log("lowstate stream OK")
        if now - latest["t"] > HEARTBEAT_TIMEOUT:
            if not warned_hb:
                log(
                    f"WARN: lowstate stopped ({HEARTBEAT_TIMEOUT:.0f}s silence) — "
                    f"network/DDS/robot issue (NOT the remote; remote-off is a physical check)"
                )
                warned_hb = True
            continue
        warned_hb = False

        keys = parse_keys(latest["remote"])
        if not primed:  # never fire buttons held at startup
            engine.prime(keys)
            primed = True
            continue
        if args.debug and keys != prev_keys:
            log(f"keys: {sorted(keys) or '—'}")
        prev_keys = keys

        for btn, action in engine.update(keys, now):
            if "play" in action or "tts" in action:
                if player.busy():
                    log(f"{btn} pressed — ignored, audio still playing")
                elif "play" in action:
                    log(f"{btn} → play {action['play']}")
                    player.play_wav(pcm_cache[btn], action["play"])
                else:
                    log(f"{btn} → tts {action['tts']!r}")
                    player.tts(action["tts"])
            elif "cmd" in action:
                log(f"{btn} → cmd: {action['cmd']}")
                try:
                    # shell=True is intentional: buttons.json is the operator's
                    # scripting surface, editable only by users who already have
                    # an SSH shell on this machine — no privilege is added.
                    subprocess.Popen(
                        action["cmd"],
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    log(f"ERROR cmd: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
        sys.exit(0)
