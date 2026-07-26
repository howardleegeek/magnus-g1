"""Pure logic for mapping wireless-remote buttons to actions. No SDK imports.

The G1's rt/lowstate messages carry the remote's raw packet in
`wireless_remote` (40 bytes). Bytes 2-3 are a 16-bit button bitfield
(xKeySwitchUnion; layout verified bit-for-bit against Unitree's official
deploy code in unitree_rl_gym remote_controller.py). This module parses that
field, validates buttons.json, and debounces presses.

Firing rules (all must hold):
  - press EDGE only (holding a button never re-fires)
  - per-button cooldown window
  - SOLO + GRACE: the button must be the ONLY key held, continuously, for
    combo_grace_sec. The robot reserves many two-key combos (L1+A damping,
    R1+X motion mode, L2+R2 debug...) — the grace window ensures an operator
    entering a system combo never fires our action, even if the two keys
    arrive a few samples apart.

Kept SDK-free so the whole thing is unit-testable off-robot.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import NamedTuple

KEY_BITS = {
    "R1": 0,
    "L1": 1,
    "START": 2,
    "SELECT": 3,
    "R2": 4,
    "L2": 5,
    "F1": 6,
    "F2": 7,
    "A": 8,
    "B": 9,
    "X": 10,
    "Y": 11,
    "UP": 12,
    "RIGHT": 13,
    "DOWN": 14,
    "LEFT": 15,
}
# Colloquial names (Calvin's guide says "RB") → canonical SDK names.
ALIASES = {"RB": "R1", "LB": "L1", "RT": "R2", "LT": "L2"}
VERBS = ("play", "cmd", "tts")  # exactly one per action


class Config(NamedTuple):
    cooldown: float
    grace: float
    volume: float | None
    mapping: dict[str, dict]
    # None = play through the robot's own speaker via the SDK. Set to route
    # "play" actions at an amplified external speaker instead (see Speaker).
    speaker: "Speaker | None" = None


class Speaker(NamedTuple):
    """An external speaker reached through PulseAudio on the Jetson.

    SDK audio (AudioClient) goes to the robot's internal speaker over DDS and
    never touches the Jetson's sound card, so a speaker plugged into the Jetson
    is silent on that path — it needs its own playback route.
    """

    sink: str  # PulseAudio sink name, or any substring of one
    gain_pct: int  # 100 = unity; PulseAudio allows software boost above that


def canon(name: str) -> str:
    up = str(name).upper()
    return ALIASES.get(up, up)


def parse_keys(wireless_remote) -> frozenset[str]:
    """40-byte remote packet -> set of held button names. Safe on short/empty input."""
    if wireless_remote is None or len(wireless_remote) < 4:
        return frozenset()
    value = wireless_remote[2] | (wireless_remote[3] << 8)
    return frozenset(k for k, bit in KEY_BITS.items() if value >> bit & 1)


def load_config(path: Path, repo_root: Path) -> Config:
    """Validate buttons.json.

    EVERY malformed input — wrong types included, not just bad JSON — must exit
    via the same SystemExit path, so the daemon's hot-reload can reject a bad
    config and keep the old one running. Nothing here may raise anything else.
    """
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise TypeError("top level must be an object")

        cooldown = float(data.get("cooldown_sec", 1.5))
        if not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError(
                f"cooldown_sec must be a finite number >= 0, got {cooldown}"
            )

        grace = float(data.get("combo_grace_sec", 0.15))
        if not math.isfinite(grace) or not 0 <= grace <= 2:
            raise ValueError(f"combo_grace_sec must be 0-2, got {grace}")

        volume = data.get("volume")
        if volume is not None:
            volume = float(volume)
            if not math.isfinite(volume) or not 0 <= volume <= 100:
                raise ValueError(f"volume must be 0-100, got {volume}")

        buttons = data.get("buttons", {})
        if not isinstance(buttons, dict):
            raise TypeError("'buttons' must be an object")

        mapping: dict[str, dict] = {}
        for btn, action in buttons.items():
            b = canon(btn)
            if b not in KEY_BITS:
                raise ValueError(
                    f"unknown button '{btn}' — valid: {sorted(KEY_BITS)} "
                    f"(aliases: {sorted(ALIASES)})"
                )
            if b in mapping:
                raise ValueError(
                    f"button '{btn}' maps to '{b}' which is already configured "
                    f"(an alias and its canonical name both point here)"
                )
            if not isinstance(action, dict) or sum(v in action for v in VERBS) != 1:
                raise ValueError(
                    f"button '{btn}': action must have exactly one of {VERBS}"
                )
            verb = next(v for v in VERBS if v in action)
            if not isinstance(action[verb], str) or not action[verb].strip():
                raise ValueError(
                    f"button '{btn}': '{verb}' value must be a non-empty string, "
                    f"got {action[verb]!r}"
                )
            if "play" in action:
                wav = repo_root / action["play"]
                if not wav.exists():
                    raise ValueError(f"button '{btn}': audio file not found: {wav}")
            mapping[b] = action
        if not mapping:
            raise ValueError("config has no buttons")

        speaker = None
        spk = data.get("external_speaker")
        if spk is not None:
            if not isinstance(spk, dict):
                raise TypeError("'external_speaker' must be an object")
            sink = spk.get("sink")
            if not isinstance(sink, str) or not sink.strip():
                raise ValueError("external_speaker.sink must be a non-empty string")
            gain = int(spk.get("gain_pct", 150))
            # PulseAudio clamps above ~153% (its own hard ceiling) and software
            # gain past that only adds distortion, so refuse it here instead.
            if not 0 < gain <= 150:
                raise ValueError(f"external_speaker.gain_pct must be 1-150, got {gain}")
            speaker = Speaker(sink.strip(), gain)

        return Config(cooldown, grace, volume, mapping, speaker)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:  # OSError, JSON, type errors — everything → one exit path
        sys.exit(f"bad config {path}: {e}")


class ButtonEngine:
    """Edge + solo-grace + cooldown state machine. update() returns actions to fire."""

    def __init__(
        self, mapping: dict[str, dict], cooldown: float = 1.5, grace: float = 0.15
    ):
        self.mapping = mapping
        self.cooldown = cooldown
        self.grace = grace
        self._prev: frozenset[str] = frozenset()
        self._pending: dict[str, float] = {}  # button -> edge time, awaiting grace
        self._last_fire: dict[str, float] = {}

    def carry_from(self, old: "ButtonEngine") -> "ButtonEngine":
        """Adopt held-key/cooldown state from the previous engine (hot-reload).

        Without this, a button held across a reload counts as a fresh press
        edge and re-fires, and all cooldown history is wiped.
        """
        self._prev = old._prev
        self._last_fire = dict(old._last_fire)
        return self

    def prime(self, keys: frozenset[str]) -> None:
        """Seed held-key state at startup so already-held buttons don't fire."""
        self._prev = keys

    def update(self, keys: frozenset[str], now: float) -> list[tuple[str, dict]]:
        # New solo press edges enter the grace queue.
        for b in keys - self._prev:
            if (
                b in self.mapping
                and keys == {b}
                and now - self._last_fire.get(b, float("-inf")) >= self.cooldown
            ):
                self._pending[b] = now
        # A pending press is cancelled the moment it stops being a solo hold.
        fired = []
        for b, t0 in list(self._pending.items()):
            if keys != {b}:
                del self._pending[b]
                continue
            if now - t0 >= self.grace:
                del self._pending[b]
                self._last_fire[b] = now
                fired.append((b, self.mapping[b]))
        self._prev = keys
        return fired
