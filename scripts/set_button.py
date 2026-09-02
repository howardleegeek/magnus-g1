#!/usr/bin/env python3
"""Point one button at one action, in place.

Run ON the robot. Exists because the alternative is a python one-liner nested
inside ssh inside PowerShell — four layers of quoting, and the failure mode is a
mangled config rather than an error.

    python3 scripts/set_button.py R1 play voices/my_line.wav
    python3 scripts/set_button.py R2 cmd  "python3 examples/arm_dance.py eth0 --routine routines/x.json"
    python3 scripts/set_button.py LB tts  "Hello and welcome."
    python3 scripts/set_button.py X  --remove

Every other button is left exactly as it was: the live config on a robot is
edited by whoever is standing in front of it, so overwriting the whole file from
a repo copy silently deletes someone else's work.
"""

from __future__ import annotations  # Jetson ships an older Python than dev laptops

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "routines" / "buttons.json"
VERBS = ("play", "tts", "cmd")
# Colloquial names people actually say, mapped to what the config uses.
ALIASES = {"RB": "R1", "LB": "L1", "RT": "R2", "LT": "L2"}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)

    button = ALIASES.get(args[0].upper(), args[0].upper())
    data = json.loads(CONFIG.read_text())
    buttons = data.setdefault("buttons", {})
    before = json.dumps(buttons.get(button))

    if len(args) == 2 and args[1] == "--remove":
        if button not in buttons:
            sys.exit(f"{button} is not mapped — nothing to remove")
        buttons.pop(button)
        after = "(unmapped)"
    else:
        if len(args) != 3:
            sys.exit(f"usage: set_button.py <button> <{'|'.join(VERBS)}> <value>")
        verb, value = args[1].lower(), args[2]
        if verb not in VERBS:
            sys.exit(f"verb must be one of {VERBS}, got {verb!r}")
        if verb == "play":
            wav = REPO_ROOT / value
            if not wav.exists():
                # The daemon rejects the whole config for this, keeping the old
                # mapping — so catch it here where the message can be useful.
                sys.exit(f"no such audio file: {wav}\n(copy it over first)")
        buttons[button] = {verb: value}
        after = json.dumps(buttons[button])

    shutil.copy(CONFIG, CONFIG.with_suffix(".json.bak"))
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print(f"{button}: {before or '(unmapped)'} -> {after}")
    print(f"previous config saved as {CONFIG.with_suffix('.json.bak').name}")
    print("\nall buttons now:")
    for b, action in buttons.items():
        print(f"  {b:3} {action}")
    print(
        "\nThe daemon hot-reloads this within ~1s — no restart needed for a "
        "mapping change.\nA NEW audio file does need one: "
        "systemctl --user restart magnus-buttons"
    )


if __name__ == "__main__":
    main()
