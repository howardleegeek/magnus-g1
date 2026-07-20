"""Grade-A dance: play a JSON routine of the G1's built-in arm actions + voice.

The robot's onboard controller keeps balance the whole time (high-level mode),
so this is safe to run free-standing on day 1.

Choreography lives in routines/*.json — edit those, not this file. Timing is
beat-based: hold = beats * 60 / bpm. A move may also speak, via either:
    "tts": "Hello!"              robot's built-in TTS
    "say": "voices/intro.wav"    pre-generated WAV (16 kHz mono 16-bit, < 3 s)
Voice fires right before the move's arm action.

Usage:
    python examples/arm_dance.py --dry-run                      # validate, no robot/SDK needed
    python examples/arm_dance.py <iface>                        # run routines/demo.json
    python examples/arm_dance.py <iface> --routine routines/x.json

Preflight first: python examples/preflight.py
"""

import argparse
import json
import sys
import time
from pathlib import Path

import voice  # sibling module: WAV validation + chunk constants

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROUTINE = REPO_ROOT / "routines" / "demo.json"


def load_routine(path: Path) -> tuple[dict, list[dict]]:
    """Return (routine_meta, moves). Each move: {action, hold, tts?, say_pcm?}."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"cannot load routine {path}: {e}")

    bpm = data.get("bpm", 100)
    default_beats = data.get("default_beats", 8)
    beat = 60.0 / bpm

    moves = []
    for i, m in enumerate(data.get("moves", [])):
        if "action" not in m:
            sys.exit(f"move #{i} missing 'action' field")
        hold = m["hold"] if "hold" in m else m.get("beats", default_beats) * beat
        move = {"action": m["action"], "hold": float(hold)}
        if "tts" in m:
            move["tts"] = m["tts"]
        if "say" in m:
            wav = REPO_ROOT / m["say"]
            pcm = voice.load_pcm(wav)  # validates 16k/mono/16-bit, exits on mismatch
            if len(pcm) > voice.CHUNK:
                sys.exit(f"move #{i}: {wav} is {len(pcm)/voice.BYTES_PER_SEC:.1f}s — "
                         f"routine clips must be < 3s (use examples/voice.py for long audio)")
            move["say_pcm"] = pcm
            move["say"] = m["say"]
        moves.append(move)

    if not moves:
        sys.exit("routine has no moves")
    if moves[-1]["action"] != "release arm":
        # Safety: never leave the arms holding a pose under load.
        moves.append({"action": "release arm", "hold": 2.0})
    return data, moves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iface", nargs="?", help="network interface, e.g. eth0 / en7")
    parser.add_argument("--routine", type=Path, default=DEFAULT_ROUTINE)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the timeline and validate; no robot, no SDK")
    args = parser.parse_args()

    data, moves = load_routine(args.routine)
    uses_voice = any("tts" in m or "say_pcm" in m for m in moves)
    total = sum(m["hold"] for m in moves)

    print(f"routine: {data.get('name', args.routine.stem)}  "
          f"({len(moves)} moves, {total:.0f}s total{', with voice' if uses_voice else ''})")
    t = 0.0
    for m in moves:
        line = m.get("tts") or m.get("say") or ""
        print(f"  {t:6.1f}s  {m['action']:<15} hold {m['hold']:.1f}s"
              + (f"   🔊 {line}" if line else ""))
        t += m["hold"]

    if args.dry_run:
        print("dry-run OK (action names are checked against the SDK at real runtime)")
        return
    if not args.iface:
        parser.error("network interface required unless --dry-run")

    # SDK imports are deferred so --dry-run works on machines without the SDK.
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map

    missing = [m["action"] for m in moves if m["action"] not in action_map]
    if missing:
        sys.exit(f"actions not in this SDK's action_map: {missing}\n"
                 f"list valid names: python examples/preflight.py --actions")

    ChannelFactoryInitialize(0, args.iface)
    client = G1ArmActionClient()
    client.SetTimeout(10.0)
    client.Init()

    audio = None
    if uses_voice:
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        audio = AudioClient()
        audio.SetTimeout(10.0)
        audio.Init()

    speaker = data.get("tts_speaker", 0)
    stream_id = str(int(time.time() * 1000))
    print("Starting — keep the e-stop remote in hand.")
    for m in moves:
        if audio and "tts" in m:
            audio.TtsMaker(m["tts"], speaker)          # speaks async on the robot
        if audio and "say_pcm" in m:
            audio.PlayStream(voice.APP, stream_id, m["say_pcm"])  # single chunk, returns fast
        print(f"  -> {m['action']}")
        client.ExecuteAction(action_map[m["action"]])
        time.sleep(m["hold"])
    if audio:
        audio.PlayStop(voice.APP)
    print("Done. Arms released.")


if __name__ == "__main__":
    main()
