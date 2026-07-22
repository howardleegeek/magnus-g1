"""Tests for the wireless-remote button engine (pure logic, no SDK)."""

import json
from pathlib import Path

import pytest

from button_engine import ButtonEngine, KEY_BITS, canon, load_config, parse_keys

REPO_ROOT = Path(__file__).resolve().parent.parent
G = 0.15  # grace used in grace-specific tests


def packet(*names):
    """Build a 40-byte wireless_remote packet with the named buttons held."""
    value = 0
    for n in names:
        value |= 1 << KEY_BITS[canon(n)]
    b = bytearray(40)
    b[2], b[3] = value & 0xFF, value >> 8
    return bytes(b)


def eng(mapping=None, cooldown=1.0, grace=0.0):
    return ButtonEngine(mapping or {"R1": {"tts": "hi"}}, cooldown, grace)


# ---- parsing ------------------------------------------------------------


def test_parse_bit_positions():
    assert parse_keys(packet("R1")) == {"R1"}
    assert parse_keys(packet("A")) == {"A"}  # high byte
    assert parse_keys(packet("R1", "A", "LEFT")) == {"R1", "A", "LEFT"}


def test_parse_garbage_safe():
    assert parse_keys(None) == frozenset()
    assert parse_keys(b"\x00") == frozenset()  # short packet


def test_aliases():
    assert canon("RB") == "R1" and canon("lb") == "L1"


# ---- debounce / edge detection (grace=0 isolates edge+cooldown logic) ----


def test_fires_once_while_held():
    e = eng()
    assert len(e.update(frozenset({"R1"}), 0.0)) == 1
    for t in (0.05, 0.10, 0.15):  # still held → no refire
        assert e.update(frozenset({"R1"}), t) == []


def test_cooldown_blocks_rapid_represses():
    e = eng(cooldown=1.5)
    assert e.update(frozenset({"R1"}), 0.0)  # press
    e.update(frozenset(), 0.2)  # release
    assert e.update(frozenset({"R1"}), 0.4) == []  # re-press inside cooldown
    e.update(frozenset(), 0.6)
    assert len(e.update(frozenset({"R1"}), 2.0)) == 1


def test_unmapped_buttons_ignored():
    assert eng().update(frozenset({"A", "X"}), 0.0) == []


# ---- combo guard (solo + grace) ------------------------------------------


def test_grace_delays_fire_until_window():
    e = eng(grace=G)
    assert e.update(frozenset({"R1"}), 0.0) == []  # edge → pending
    assert e.update(frozenset({"R1"}), 0.05) == []  # inside grace
    assert len(e.update(frozenset({"R1"}), 0.20)) == 1  # solo through grace


def test_system_combo_does_not_fire_second_key_joins():
    # Operator presses R1 then X (motion-mode combo) within the grace window.
    e = eng(grace=G)
    assert e.update(frozenset({"R1"}), 0.0) == []
    assert e.update(frozenset({"R1", "X"}), 0.05) == []  # combo → cancelled
    assert e.update(frozenset({"R1", "X"}), 0.30) == []  # never fires
    e.update(frozenset(), 0.4)  # release all
    assert e.update(frozenset({"R1"}), 5.0) == []  # clean solo re-press pends
    assert len(e.update(frozenset({"R1"}), 5.2)) == 1  # and fires after grace


def test_press_while_other_key_held_never_pends():
    # L2 already held, then R2 pressed (debug-mode combo) — R2 mapped or not,
    # a non-solo press must not enter the pipeline.
    e = eng({"R2": {"tts": "x"}}, grace=G)
    e.update(frozenset({"L2"}), 0.0)
    assert e.update(frozenset({"L2", "R2"}), 0.1) == []
    assert e.update(frozenset({"L2", "R2"}), 0.5) == []


def test_release_before_grace_cancels():
    e = eng(grace=G)
    assert e.update(frozenset({"R1"}), 0.0) == []
    assert e.update(frozenset(), 0.05) == []  # released early
    assert e.update(frozenset(), 0.30) == []  # nothing fires late


# ---- reload/startup state carry ------------------------------------------


def test_carry_from_prevents_refire_across_reload():
    e1 = eng()
    assert e1.update(frozenset({"R1"}), 0.0)  # fired once
    e2 = eng(cooldown=1.0).carry_from(e1)  # "hot reload"
    assert e2.update(frozenset({"R1"}), 0.1) == []  # still held → no edge
    assert e2.update(frozenset({"R1"}), 0.9) == []  # cooldown carried too


def test_prime_swallows_held_at_startup():
    e = eng()
    e.prime(frozenset({"R1"}))
    assert e.update(frozenset({"R1"}), 0.0) == []  # held at boot → no fire
    e.update(frozenset(), 0.1)
    assert len(e.update(frozenset({"R1"}), 2.0)) == 1  # real press works


# ---- config validation ----------------------------------------------------


def write_cfg(tmp_path, payload, raw=None):
    p = tmp_path / "buttons.json"
    p.write_text(raw if raw is not None else json.dumps(payload))
    return p


def test_shipped_config_valid():
    cfg = load_config(REPO_ROOT / "routines" / "buttons.json", REPO_ROOT)
    assert "R1" in cfg.mapping and cfg.cooldown > 0 and cfg.volume == 85


def test_unknown_button_rejected(tmp_path):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"Q9": {"tts": "x"}}}), REPO_ROOT)


def test_action_needs_exactly_one_verb(tmp_path):
    with pytest.raises(SystemExit):
        load_config(
            write_cfg(tmp_path, {"buttons": {"RB": {"tts": "x", "cmd": "y"}}}),
            REPO_ROOT,
        )
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, {"buttons": {"RB": {}}}), REPO_ROOT)


def test_missing_audio_file_rejected(tmp_path):
    with pytest.raises(SystemExit):
        load_config(
            write_cfg(tmp_path, {"buttons": {"RB": {"play": "voices/nope.wav"}}}),
            REPO_ROOT,
        )


# every malformed-TYPE input must exit via SystemExit, never raise raw —
# the daemon's hot-reload guarantee depends on it
@pytest.mark.parametrize(
    "payload",
    [
        {"cooldown_sec": "1.5s", "buttons": {"RB": {"tts": "x"}}},  # ValueError
        {"cooldown_sec": None, "buttons": {"RB": {"tts": "x"}}},  # TypeError
        {"buttons": [{"tts": "x"}]},  # AttributeError path
        {"buttons": {"RB": {"play": 123}}},  # non-str play
        {"buttons": {"RB": {"tts": 12345}}},  # non-str tts → would crash on press
        {
            "buttons": {"RB": {"cmd": ["ls", "-la"]}}
        },  # list cmd → Popen runs first elem only
        {"buttons": {"RB": {"tts": "   "}}},  # blank tts
        {
            "buttons": {"RB": {"tts": "x"}, "R1": {"tts": "y"}}
        },  # alias+canonical collision
        {"volume": 150, "buttons": {"RB": {"tts": "x"}}},  # out of range
        {"combo_grace_sec": 99, "buttons": {"RB": {"tts": "x"}}},  # out of range
    ],
)
def test_malformed_types_exit_cleanly(tmp_path, payload):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, payload), REPO_ROOT)


def test_nan_cooldown_rejected(tmp_path):
    raw = '{"cooldown_sec": NaN, "buttons": {"RB": {"tts": "x"}}}'  # json accepts NaN!
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, None, raw=raw), REPO_ROOT)


def test_toplevel_array_rejected(tmp_path):
    with pytest.raises(SystemExit):
        load_config(write_cfg(tmp_path, None, raw='["not", "an", "object"]'), REPO_ROOT)
