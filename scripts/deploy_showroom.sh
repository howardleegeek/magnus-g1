#!/usr/bin/env bash
# PLUG-AND-PLAY showroom deploy: run this at the robot, walk away with RB working.
#
#   1. cable in neck RJ45, laptop IP 192.168.123.222 (checklist Part 1-2)
#   2. ./scripts/deploy_showroom.sh          # or --dry-run to preview
#
# Does: onboard install (repo+SDK+voices into the Jetson) -> speaker verify ->
# mpg123 fallback (best-effort) -> systemd service installed+started ->
# live RB test prompt. Re-run anytime: every step is idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

PC2="${PC2_USER:-unitree}@${PC2_IP:-192.168.123.164}"
DRY="${1:-}"
step() { printf '\n=== %s\n' "$*"; }
run()  { if [ "$DRY" = "--dry-run" ]; then echo "DRY: $*"; else "$@"; fi }

step "A. base install into the robot (repo + SDK + voices + tests)"
if [ "$DRY" = "--dry-run" ]; then
    ./scripts/install_onboard.sh --dry-run
else
    ./scripts/install_onboard.sh
fi

step "B. mpg123 fallback player (best-effort — Jetson may lack internet)"
run ssh "$PC2" 'command -v mpg123 >/dev/null && echo "mpg123 already installed" || \
    { sudo apt-get -y install mpg123 2>/dev/null && echo "mpg123 installed" || \
      echo "WARN: no internet on Jetson — skipping mpg123 (AudioClient path still works)"; }'

step "C. speaker + welcome file verification (you should HEAR the welcome line)"
run ssh "$PC2" 'cd magnus && IFACE=$(ip -o -4 addr show | awk "\$4 ~ /192\.168\.123/ {print \$2; exit}") && \
    ./venv/bin/python magnus-g1/examples/voice.py "$IFACE" --volume 85 && \
    ./venv/bin/python magnus-g1/examples/voice.py "$IFACE" --play magnus-g1/voices/showroom_welcome.wav'

step "D. install + start the button service (survives reboots, auto-restarts)"
run ssh "$PC2" 'sudo cp /home/unitree/magnus/magnus-g1/deploy/magnus-buttons.service /etc/systemd/system/ && \
    sudo systemctl daemon-reload && sudo systemctl enable magnus-buttons && \
    sudo systemctl restart magnus-buttons && sleep 2 && \
    sudo systemctl is-active magnus-buttons && \
    sudo journalctl -u magnus-buttons -n 5 --no-pager'

step "E. LIVE TEST"
printf '\n>>> Press RB on the wireless controller NOW.\n'
printf '>>> Expected: robot says the welcome line. Press again during playback: ignored (by design).\n'
printf '>>> Watch logs:   ssh %s "sudo journalctl -u magnus-buttons -f"\n' "$PC2"
printf '>>> Change behavior later WITHOUT this laptop: edit routines/buttons.json on the\n'
printf '>>> robot (or rsync it) — the service hot-reloads in ~1s. New voice lines: add to\n'
printf '>>> voices/lines.txt, run scripts/build_voices.sh, re-run this script.\n'
