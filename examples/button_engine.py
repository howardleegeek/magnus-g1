"""Pure logic for mapping wireless-remote buttons to actions. No SDK imports.

The G1's rt/lowstate messages carry the remote's raw packet in
`wireless_remote` (40 bytes). Bytes 2-3 are a 16-bit button bitfield
(xKeySwitchUnion in the official SDK headers). This module parses that field,
validates the buttons.json config, and debounces presses: an action fires on
the press EDGE (not while held) and never more than once per cooldown window.

Kept SDK-free so the whole thing is unit-testable off-robot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KEY_BITS = {
    "R1": 0, "L1": 1, "START": 2, "SELECT": 3,
    "R2": 4, "L2": 5, "F1": 6, "F2": 7,
    "A": 8, "B": 9, "X": 10, "Y": 11,
    "UP": 12, "RIGHT": 13, "DOWN": 14, "LEFT": 15,
}
# Colloquial names (Calvin's guide says "RB") → canonical SDK names.
ALIASES = {"RB": "R1", "LB": "L1", "RT": "R2", "LT": "L2"}
VERBS = ("play", "cmd", "tts")   # exactly one per action


def canon(name: str) -> str:
    up = name.upper()
    return ALIASES.get(up, up)


def parse_keys(wireless_remote) -> frozenset[str]:
    """40-byte remote packet -> set of held button names. Safe on short/empty input."""
    if wireless_remote is None or len(wireless_remote) < 4:
        return frozenset()
    value = wireless_remote[2] | (wireless_remote[3] << 8)
    return frozenset(k for k, bit in KEY_BITS.items() if value >> bit & 1)


def load_config(path: Path, repo_root: Path) -> tuple[float, dict[str, dict]]:
    """Validate buttons.json. Returns (cooldown_sec, {canonical_button: action}).

    Fails loudly (SystemExit) on unknown buttons, malformed actions, or missing
    audio files — a bad config should never reach the robot silently.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"cannot load config {path}: {e}")

    cooldown = float(data.get("cooldown_sec", 1.5))
    mapping: dict[str, dict] = {}
    for btn, action in data.get("buttons", {}).items():
        b = canon(btn)
        if b not in KEY_BITS:
            sys.exit(f"unknown button '{btn}' — valid: {sorted(KEY_BITS)} "
                     f"(aliases: {sorted(ALIASES)})")
        if not isinstance(action, dict) or sum(v in action for v in VERBS) != 1:
            sys.exit(f"button '{btn}': action must have exactly one of {VERBS}")
        if "play" in action and not (repo_root / action["play"]).exists():
            sys.exit(f"button '{btn}': audio file not found: {repo_root / action['play']}")
        mapping[b] = action
    if not mapping:
        sys.exit(f"{path}: config has no buttons")
    return cooldown, mapping


class ButtonEngine:
    """Edge detection + per-button cooldown. update() returns actions to fire."""

    def __init__(self, mapping: dict[str, dict], cooldown: float = 1.5):
        self.mapping = mapping
        self.cooldown = cooldown
        self._prev: frozenset[str] = frozenset()
        self._last_fire: dict[str, float] = {}

    def update(self, keys: frozenset[str], now: float) -> list[tuple[str, dict]]:
        fired = []
        for b in keys - self._prev:                      # press edges only
            if b in self.mapping and now - self._last_fire.get(b, float("-inf")) >= self.cooldown:
                self._last_fire[b] = now
                fired.append((b, self.mapping[b]))
        self._prev = keys
        return fired
