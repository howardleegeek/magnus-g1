"""Tests for the wireless-remote button engine (pure logic, no SDK)."""

import json
from pathlib import Path

import pytest

from button_engine import ButtonEngine, KEY_BITS, canon, load_config, parse_keys

REPO_ROOT = Path(__file__).resolve().parent.parent


def packet(*names):
    """Build a 40-byte wireless_remote packet with the named buttons held."""
    value = 0
    for n in names:
        value |= 1 << KEY_BITS[canon(n)]
    b = bytearray(40)
    b[2], b[3] = value & 0xFF, value >> 8
    return bytes(b)


# ---- parsing ------------------------------------------------------------

def test_parse_bit_positions():
    assert parse_keys(packet("R1")) == {"R1"}
    assert parse_keys(packet("A")) == {"A"}          # high byte
    assert parse_keys(packet("R1", "A", "LEFT")) == {"R1", "A", "LEFT"}


def test_parse_garbage_safe():
    assert parse_keys(None) == frozenset()
    assert parse_keys(b"\x00") == frozenset()        # short packet


def test_aliases():
    assert canon("RB") == "R1" and canon("lb") == "L1"


# ---- debounce / edge detection ------------------------------------------

def test_fires_once_while_held():
    eng = ButtonEngine({"R1": {"tts": "hi"}}, cooldown=1.0)
    assert len(eng.update(frozenset({"R1"}), now=0.0)) == 1
    for t in (0.05, 0.10, 0.15):                     # still held → no refire
        assert eng.update(frozenset({"R1"}), now=t) == []


def test_cooldown_blocks_rapid_represses():
    eng = ButtonEngine({"R1": {"tts": "hi"}}, cooldown=1.5)
    assert eng.update(frozenset({"R1"}), 0.0)        # press
    eng.update(frozenset(), 0.2)                     # release
    assert eng.update(frozenset({"R1"}), 0.4) == []  # re-press inside cooldown
    eng.update(frozenset(), 0.6)
    assert len(eng.update(frozenset({"R1"}), 2.0)) == 1  # after cooldown


def test_unmapped_buttons_ignored():
    eng = ButtonEngine({"R1": {"tts": "hi"}}, cooldown=0)
    assert eng.update(frozenset({"A", "X"}), 0.0) == []


# ---- config validation ---------------------------------------------------

def write_cfg(tmp_path, payload):
    p = tmp_path / "buttons.json"
    p.write_text(json.dumps(payload))
    return p


def test_shipped_config_valid():
    cooldown, mapping = load_config(REPO_ROOT / "routines" / "buttons.json", REPO_ROOT)
    assert "R1" in mapping and cooldown > 0


def test_unknown_button_rejected(tmp_path):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"Q9": {"tts": "x"}}}), REPO_ROOT)


def test_action_needs_exactly_one_verb(tmp_path):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"RB": {"tts": "x", "cmd": "y"}}}), REPO_ROOT)
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"RB": {}}}), REPO_ROOT)


def test_missing_audio_file_rejected(tmp_path):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"RB": {"play": "voices/nope.wav"}}}), REPO_ROOT)
