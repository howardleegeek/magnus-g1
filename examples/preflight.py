"""Gate 0 preflight — run this before any robot session.

Automates the SOP Gate 0 checklist: network link, SDK install, action map.
Exit code 0 = all checks passed (safe to proceed to arm_dance.py).

Usage:
    python examples/preflight.py            # network + SDK checks
    python examples/preflight.py --actions  # also dump the SDK's arm action names
"""

from __future__ import annotations  # Jetson ships an older Python than dev laptops

import argparse
import shutil
import subprocess
import sys

ROBOT_IP = "192.168.123.161"

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--actions",
        action="store_true",
        help="dump arm action names from the installed SDK",
    )
    args = parser.parse_args()

    # 1. Robot reachable
    ping = shutil.which("ping")
    if ping:
        r = subprocess.run(
            [ping, "-c", "2", "-W", "2", ROBOT_IP], capture_output=True, text=True
        )
        check(
            f"robot reachable at {ROBOT_IP}",
            r.returncode == 0,
            (
                "check Ethernet link + laptop static IP 192.168.123.x"
                if r.returncode
                else ""
            ),
        )
    else:
        check("ping available", False, "no ping binary on PATH")

    # 2. SDK importable
    try:
        import unitree_sdk2py  # noqa: F401

        check("unitree_sdk2py installed", True)
        sdk_ok = True
    except ImportError as e:
        check(
            "unitree_sdk2py installed",
            False,
            f"{e} — pip install -e <path-to>/unitree_sdk2_python",
        )
        sdk_ok = False

    # 3. Arm action map loads (and optionally dump it)
    if sdk_ok:
        try:
            from unitree_sdk2py.g1.arm.g1_arm_action_client import action_map

            check("arm action_map loads", True, f"{len(action_map)} actions")
            if args.actions:
                for name in sorted(action_map):
                    print(f"    - {name}")
        except Exception as e:
            check("arm action_map loads", False, str(e))

    print()
    if all(results):
        print("GATE 0 checks PASSED. Remaining manual items: e-stop test mid-command,")
        print("one high-level command executed. Then proceed to arm_dance.py.")
        return 0
    print("GATE 0 FAILED — fix the items above before touching the robot.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
