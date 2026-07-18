"""Grade-A dance: play a JSON routine of the G1's built-in arm actions.

The robot's onboard controller keeps balance the whole time (high-level mode),
so this is safe to run free-standing on day 1.

Choreography lives in routines/*.json — edit those, not this file. Timing is
beat-based: hold = beats * 60 / bpm, so the routine stays synced to your track.

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

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROUTINE = REPO_ROOT / "routines" / "demo.json"


def load_routine(path: Path) -> tuple[str, list[tuple[str, float]]]:
    """Return (name, [(action, hold_seconds), ...]). Raises SystemExit on bad input."""
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
        moves.append((m["action"], float(hold)))

    if not moves:
        sys.exit("routine has no moves")
    if moves[-1][0] != "release arm":
        # Safety: never leave the arms holding a pose under load.
        moves.append(("release arm", 2.0))
    return data.get("name", path.stem), moves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iface", nargs="?", help="network interface, e.g. eth0 / en7")
    parser.add_argument("--routine", type=Path, default=DEFAULT_ROUTINE)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the timeline and validate; no robot, no SDK")
    args = parser.parse_args()

    name, moves = load_routine(args.routine)
    total = sum(h for _, h in moves)

    print(f"routine: {name}  ({len(moves)} moves, {total:.0f}s total)")
    t = 0.0
    for action, hold in moves:
        print(f"  {t:6.1f}s  {action:<15} hold {hold:.1f}s")
        t += hold

    if args.dry_run:
        print("dry-run OK (action names are checked against the SDK at real runtime)")
        return
    if not args.iface:
        parser.error("network interface required unless --dry-run")

    # SDK imports are deferred so --dry-run works on machines without the SDK.
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map

    missing = [a for a, _ in moves if a not in action_map]
    if missing:
        sys.exit(f"actions not in this SDK's action_map: {missing}\n"
                 f"list valid names: python examples/preflight.py --actions")

    ChannelFactoryInitialize(0, args.iface)
    client = G1ArmActionClient()
    client.SetTimeout(10.0)
    client.Init()

    print("Starting — keep the e-stop remote in hand.")
    for action, hold in moves:
        print(f"  -> {action}")
        client.ExecuteAction(action_map[action])
        time.sleep(hold)
    print("Done. Arms released.")


if __name__ == "__main__":
    main()
