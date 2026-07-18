"""Grade-A dance: sequence the G1's built-in arm actions into a routine.

The robot's onboard controller keeps balance the whole time (high-level mode),
so this is safe to run free-standing on day 1.

Usage:
    python examples/arm_dance.py <network-interface>   # e.g. eth0 / en7

List the action names your installed SDK version supports:
    python -c "from unitree_sdk2py.g1.arm.g1_arm_action_client import action_map; print(sorted(action_map))"

Requires: unitree_sdk2_python installed, laptop on 192.168.123.x, robot in
normal (balanced stand / motion) mode via the remote or app.
"""

import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map

# Routine: (action name, seconds to hold before the next move).
# Names must exist in action_map — verify with the one-liner in the docstring;
# they occasionally change between SDK releases.
ROUTINE = [
    ("high wave", 3.0),
    ("clap", 3.0),
    ("heart", 3.0),
    ("hands up", 3.0),
    ("high five", 3.0),
    ("hug", 3.0),
    ("high wave", 3.0),
    ("release arm", 2.0),  # always end by releasing the arms
]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <network-interface>")

    ChannelFactoryInitialize(0, sys.argv[1])

    client = G1ArmActionClient()
    client.SetTimeout(10.0)
    client.Init()

    missing = [name for name, _ in ROUTINE if name not in action_map]
    if missing:
        sys.exit(f"actions not in this SDK's action_map: {missing} — "
                 f"run the list one-liner in the docstring and edit ROUTINE")

    print("Starting routine — keep the e-stop remote in hand.")
    for name, hold in ROUTINE:
        print(f"  -> {name}")
        client.ExecuteAction(action_map[name])
        time.sleep(hold)

    print("Done. Arms released.")


if __name__ == "__main__":
    main()
