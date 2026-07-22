"""Robot-free tests for the routine engine and WAV validation.

Covers everything that can break BEFORE a robot session. Robot-tier checks
(speaker playback, action execution) live in the SOP's on-robot gates.
"""

import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest

import voice
from arm_dance import load_routine, DEFAULT_ROUTINE, REPO_ROOT


def write_routine(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "r.json"
    p.write_text(json.dumps(payload))
    return p


def write_wav(path: Path, seconds: float, rate: int = 16000, channels: int = 1,
              width: int = 2) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00" * int(rate * seconds * channels * width))
    return path


# ---- routine engine ----------------------------------------------------

def test_demo_routine_loads_and_is_voice_ready():
    data, moves = load_routine(DEFAULT_ROUTINE)
    assert moves, "demo routine must have moves"
    assert moves[-1]["action"] == "release arm"
    assert any("say_pcm" in m or "tts" in m for m in moves), "demo should include a voice line"


def test_beat_math(tmp_path):
    r = write_routine(tmp_path, {"bpm": 120, "default_beats": 4,
                                 "moves": [{"action": "clap"},
                                           {"action": "hug", "beats": 2},
                                           {"action": "release arm", "hold": 1.5}]})
    _, moves = load_routine(r)
    assert moves[0]["hold"] == pytest.approx(2.0)   # 4 beats at 120bpm
    assert moves[1]["hold"] == pytest.approx(1.0)   # 2 beats
    assert moves[2]["hold"] == pytest.approx(1.5)   # explicit hold wins


def test_release_arm_auto_appended(tmp_path):
    r = write_routine(tmp_path, {"moves": [{"action": "clap"}]})
    _, moves = load_routine(r)
    assert moves[-1]["action"] == "release arm"


def test_missing_action_rejected(tmp_path):
    r = write_routine(tmp_path, {"moves": [{"beats": 4}]})
    with pytest.raises(SystemExit):
        load_routine(r)


def test_empty_routine_rejected(tmp_path):
    r = write_routine(tmp_path, {"moves": []})
    with pytest.raises(SystemExit):
        load_routine(r)


def test_bad_json_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(SystemExit):
        load_routine(p)


# ---- WAV validation ----------------------------------------------------

def test_valid_wav_accepted(tmp_path):
    p = write_wav(tmp_path / "ok.wav", seconds=1.0)
    pcm = voice.load_pcm(p)
    assert len(pcm) == 32000  # 1s at 16kHz 16-bit mono


def test_wrong_rate_rejected(tmp_path):
    p = write_wav(tmp_path / "cd.wav", seconds=0.5, rate=44100, channels=2)
    with pytest.raises(SystemExit):
        voice.load_pcm(p)


def test_garbage_file_rejected(tmp_path):
    p = tmp_path / "junk.wav"
    p.write_bytes(b"not a wav at all")
    with pytest.raises(SystemExit):
        voice.load_pcm(p)


def test_long_clip_rejected_in_routine(tmp_path):
    # >3s (one chunk) clips must be refused inside routines
    long_wav = write_wav(tmp_path / "long.wav", seconds=4.0)
    r = write_routine(tmp_path, {"moves": [{"action": "clap", "say": str(long_wav)},
                                           {"action": "release arm"}]})
    with pytest.raises(SystemExit):
        load_routine(r)


def test_shipped_intro_wav_is_routine_safe():
    pcm = voice.load_pcm(REPO_ROOT / "voices" / "intro.wav")
    assert 0 < len(pcm) <= voice.CHUNK


# ---- stream timing (regression: exact-multiple files lost their last second)

class FakeAudioClient:
    def __init__(self):
        self.stopped = False
    def PlayStream(self, app, sid, chunk):
        return 0
    def PlayStop(self, app):
        self.stopped = True


@pytest.mark.parametrize("nbytes", [voice.CHUNK, 2 * voice.CHUNK, voice.CHUNK + 1000])
def test_stream_wav_waits_out_full_audio(monkeypatch, nbytes):
    slept = []
    monkeypatch.setattr(voice.time, "sleep", lambda s: slept.append(s))
    client = FakeAudioClient()
    voice.stream_wav(client, b"\x00" * nbytes)
    assert client.stopped
    assert sum(slept) >= nbytes / voice.BYTES_PER_SEC  # never PlayStop early


# ---- CLI smoke ---------------------------------------------------------

def test_dry_run_cli_exits_zero():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "examples" / "arm_dance.py"),
                        "--dry-run"], capture_output=True, text=True, cwd=REPO_ROOT)
    assert r.returncode == 0, r.stderr
    assert "dry-run OK" in r.stdout


def test_voice_check_cli(tmp_path):
    p = write_wav(tmp_path / "ok.wav", seconds=1.0)
    r = subprocess.run([sys.executable, str(REPO_ROOT / "examples" / "voice.py"),
                        "--check", str(p)], capture_output=True, text=True)
    assert r.returncode == 0 and "routine-safe" in r.stdout


def test_missing_iface_errors():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "examples" / "arm_dance.py")],
                       capture_output=True, text=True, cwd=REPO_ROOT)
    assert r.returncode != 0
    assert "network interface required" in r.stderr
