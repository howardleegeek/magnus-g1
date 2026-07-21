#!/usr/bin/env bash
# One-shot onboard install: push this repo + SDK INTO the G1's internal
# computer (PC2), install there, verify there, and end with the robot speaking.
#
# Run from the laptop, repo root, with the neck Ethernet cable connected:
#     ./scripts/install_onboard.sh              # full install + audible smoke test
#     ./scripts/install_onboard.sh --dry-run    # show plan, touch nothing
#
# Prereqs: laptop IP 192.168.123.222 set, unitree_sdk2_python cloned as a
# sibling of this repo (../unitree_sdk2_python). Password prompts: run the
# offered ssh-copy-id once and the rest is passwordless.
set -euo pipefail
cd "$(dirname "$0")/.."

ROBOT_IP="192.168.123.161"
PC2="${PC2_USER:-unitree}@${PC2_IP:-192.168.123.164}"
SDK_DIR="../unitree_sdk2_python"
DRY="${1:-}"

step() { printf '\n=== %s\n' "$*"; }
run()  { if [ "$DRY" = "--dry-run" ]; then echo "DRY: $*"; else "$@"; fi }

step "1/6 connectivity"
if ping -c 2 -W 2 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "robot OK"
elif [ "$DRY" = "--dry-run" ]; then
    echo "DRY: robot $ROBOT_IP unreachable (fine for dry-run; hard FAIL in real run)"
else
    echo "FAIL: robot $ROBOT_IP unreachable — cable/IP (checklist Part 2)"; exit 1
fi
if [ ! -d "$SDK_DIR" ]; then
    [ "$DRY" = "--dry-run" ] && echo "DRY: $SDK_DIR missing (would FAIL real run)" || \
        { echo "FAIL: $SDK_DIR missing — git clone https://github.com/unitreerobotics/unitree_sdk2_python ../"; exit 1; }
fi

step "2/6 ssh access to PC2 ($PC2)"
if [ "$DRY" = "--dry-run" ]; then
    echo "DRY: would verify ssh key, run ssh-copy-id if missing"
elif ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$PC2" true 2>/dev/null; then
    echo "No ssh key on PC2 yet — installing one (enter the PC2 password when asked; default is often '123' — change it after!)"
    run ssh-copy-id "$PC2"
fi
run ssh "$PC2" 'echo "PC2 OK: $(uname -m), $(python3 --version 2>&1)"'

step "3/6 push repo + SDK + voice pack into the robot"
run rsync -a --delete --exclude .git --exclude .venv --exclude __pycache__ ./ "$PC2":magnus/magnus-g1/
run rsync -a --delete --exclude .git "$SDK_DIR"/ "$PC2":magnus/unitree_sdk2_python/

step "4/6 install on PC2"
run ssh "$PC2" 'cd magnus && { [ -d venv ] || python3 -m venv venv; } && \
    ./venv/bin/pip -q install -e ./unitree_sdk2_python pytest 2>&1 | tail -2 || \
    echo "WARN: pip needed internet it may not have — see ONBOARD-INSTALL.md wheels note"'

step "5/6 verify ONBOARD (the 14-test gate, running inside the robot)"
run ssh "$PC2" 'cd magnus && ./venv/bin/python -m pytest magnus-g1/tests/ -q'

step "6/6 audible smoke test — the robot announces itself"
IFACE_CMD='ip -o -4 addr show | awk "\$4 ~ /192\.168\.123/ {print \$2; exit}"'
run ssh "$PC2" "cd magnus && IFACE=\$($IFACE_CMD) && echo \"PC2 iface: \$IFACE\" && \
    ./venv/bin/python magnus-g1/examples/voice.py \"\$IFACE\" --volume 60 && \
    ./venv/bin/python magnus-g1/examples/voice.py \"\$IFACE\" --play magnus-g1/voices/intro.wav"

printf '\nINSTALLED. If you heard the robot speak, the stack lives inside it now.\n'
printf 'Laptop-free run:  ssh %s "cd magnus && ./venv/bin/python magnus-g1/examples/arm_dance.py eth0"\n' "$PC2"
printf 'Update later: re-run this script (rsync is incremental).\n'
