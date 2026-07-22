#!/usr/bin/env bash
# One-shot onboard install: push this repo + SDK INTO the G1's internal
# computer (PC2, Jetson), install there, verify there, end with the robot speaking.
#
# Run from the laptop, repo root, with the neck Ethernet cable connected:
#     ./scripts/install_onboard.sh              # full install + audible smoke test
#     ./scripts/install_onboard.sh --dry-run    # show plan, touch nothing
#
# SDK source: accepts ../unitree_sdk2_python (sibling) OR ./unitree_sdk2_python
# (the SETUP.md layout). Password prompts: the offered ssh-copy-id runs once,
# then everything is passwordless.
set -euo pipefail
cd "$(dirname "$0")/.."

ROBOT_IP="192.168.123.161"
PC2="${PC2_USER:-unitree}@${PC2_IP:-192.168.123.164}"
DRY="${1:-}"

SDK_DIR=""
for d in ../unitree_sdk2_python ./unitree_sdk2_python; do
    [ -d "$d" ] && SDK_DIR="$d" && break
done

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
if [ -z "$SDK_DIR" ]; then
    MSG="unitree_sdk2_python not found — run: git clone https://github.com/unitreerobotics/unitree_sdk2_python \"$(cd .. && pwd)/unitree_sdk2_python\""
    [ "$DRY" = "--dry-run" ] && echo "DRY: $MSG (would FAIL real run)" || { echo "FAIL: $MSG"; exit 1; }
else
    echo "SDK source: $SDK_DIR"
fi

step "2/6 ssh access to PC2 ($PC2)"
if [ "$DRY" = "--dry-run" ]; then
    echo "DRY: would verify ssh key, run ssh-copy-id if missing, probe python/SDK"
elif ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$PC2" true 2>/dev/null; then
    echo "No ssh key on PC2 yet — installing one (enter the PC2 password when asked; default is often '123' — change it after with 'passwd'!)"
    run ssh-copy-id "$PC2"
fi
run ssh "$PC2" 'echo "PC2 OK: $(uname -m), $(python3 --version 2>&1)"; python3 -c "import unitree_sdk2py" 2>/dev/null && echo "factory SDK: present (system)" || echo "factory SDK: not importable system-wide"'

step "3/6 push repo + SDK + voice pack + wheelhouse into the robot"
run ssh "$PC2" 'mkdir -p magnus'
run rsync -a --delete --exclude .git --exclude .venv --exclude __pycache__ --exclude unitree_sdk2_python ./ "$PC2":magnus/magnus-g1/
run rsync -a --delete --exclude .git "$SDK_DIR"/ "$PC2":magnus/unitree_sdk2_python/
run rsync -a deploy/wheels/ "$PC2":magnus/wheels/

step "4/6 install on PC2 (venv sees factory system packages; offline-tolerant)"
run ssh "$PC2" 'set -o pipefail; cd magnus && { [ -d venv ] || python3 -m venv --system-site-packages venv; } && \
    if ./venv/bin/python -c "import unitree_sdk2py" 2>/dev/null; then \
        echo "SDK already importable in venv — skipping SDK pip install"; \
    else \
        ./venv/bin/pip -q install -e ./unitree_sdk2_python 2>&1 | tail -3 || \
        echo "WARN: SDK pip install failed (no internet / cyclonedds build?) — see ONBOARD-INSTALL.md"; \
    fi; \
    ./venv/bin/python -c "import pytest" 2>/dev/null || \
        ./venv/bin/pip -q install --no-index --find-links ./wheels pytest && echo "pytest ready (wheelhouse)"'

step "5/6 verify ONBOARD (gates degrade loudly, never silently)"
run ssh "$PC2" 'cd magnus && \
    if ./venv/bin/python -c "import pytest" 2>/dev/null; then \
        ./venv/bin/python -m pytest magnus-g1/tests/ -q; \
    else \
        echo "WARN: pytest unavailable — falling back to import gate"; \
    fi && \
    ./venv/bin/python -c "import unitree_sdk2py; print(\"SDK import: OK\")"'

step "6/6 audible smoke test — the robot announces itself"
IFACE_CMD='ip -o -4 addr show | awk "\$4 ~ /192\.168\.123/ {print \$2; exit}"'
run ssh "$PC2" "cd magnus && IFACE=\$($IFACE_CMD) && echo \"PC2 iface: \$IFACE\" && \
    ./venv/bin/python magnus-g1/examples/voice.py \"\$IFACE\" --volume 60 && \
    ./venv/bin/python magnus-g1/examples/voice.py \"\$IFACE\" --play magnus-g1/voices/intro.wav"

printf '\nINSTALLED. If you heard the robot speak, the stack lives inside it now.\n'
printf 'Laptop-free run:  ssh %s "cd magnus && ./venv/bin/python magnus-g1/examples/arm_dance.py eth0"\n' "$PC2"
printf 'Update later: re-run this script (rsync is incremental).\n'
