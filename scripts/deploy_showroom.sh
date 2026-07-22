#!/usr/bin/env bash
# PLUG-AND-PLAY showroom deploy: run this at the robot, walk away with RB working.
#
#   1. cable in neck RJ45, laptop IP 192.168.123.222 (checklist Parts 1-2)
#   2. ./scripts/deploy_showroom.sh          # or --dry-run to preview
#
# Does: onboard install (repo+SDK+voices into the Jetson) -> speaker verify ->
# systemd service installed with the DETECTED interface + started -> gated live
# RB test (checks the daemon's log actually fired). Re-run anytime: idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

PC2="${PC2_USER:-unitree}@${PC2_IP:-192.168.123.164}"
DRY="${1:-}"
step() { printf '\n=== %s\n' "$*"; }
run()  { if [ "$DRY" = "--dry-run" ]; then echo "DRY: $*"; else "$@"; fi }

step "A. base install into the robot (repo + SDK + voices + tests)"
if [ "$DRY" = "--dry-run" ]; then ./scripts/install_onboard.sh --dry-run; else ./scripts/install_onboard.sh; fi

step "B. detect the Jetson's robot-LAN interface (eth0 vs eth1 varies by unit)"
if [ "$DRY" = "--dry-run" ]; then
    IFACE="eth0"; echo "DRY: would detect via ip -o -4 addr show (assuming eth0)"
else
    IFACE=$(ssh "$PC2" 'ip -o -4 addr show | awk "\$4 ~ /192\.168\.123/ {print \$2; exit}"')
    [ -n "$IFACE" ] || { echo "FAIL: could not detect PC2 interface"; exit 1; }
    echo "PC2 interface: $IFACE"
fi

step "C. speaker + welcome file verification (you should HEAR the welcome line)"
run ssh "$PC2" "cd magnus && \
    ./venv/bin/python magnus-g1/examples/voice.py $IFACE --volume 85 && \
    ./venv/bin/python magnus-g1/examples/voice.py $IFACE --play magnus-g1/voices/showroom_welcome.wav"

step "D. install + start the button service (detected iface baked in; survives reboots)"
run ssh -t "$PC2" "sed 's/button_trigger.py eth0/button_trigger.py $IFACE/' \
        /home/unitree/magnus/magnus-g1/deploy/magnus-buttons.service | sudo tee /etc/systemd/system/magnus-buttons.service >/dev/null && \
    sudo usermod -aG systemd-journal unitree 2>/dev/null; \
    sudo systemctl daemon-reload && sudo systemctl enable magnus-buttons && \
    sudo systemctl restart magnus-buttons && sleep 2 && sudo systemctl is-active magnus-buttons && \
    sleep 8 && sudo systemctl is-active magnus-buttons && \
    sudo journalctl -u magnus-buttons -n 6 --no-pager"

step "E. GATED LIVE TEST"
if [ "$DRY" = "--dry-run" ]; then
    echo "DRY: would prompt for an RB press, then verify a '→ play' line in the service journal"
else
    printf '\n>>> Press RB on the wireless controller NOW, wait for the welcome line to finish,\n'
    printf '>>> then press ENTER here to verify...\n'
    read -r
    if ssh -t "$PC2" "journalctl -u magnus-buttons -S -120s --no-pager 2>/dev/null || sudo journalctl -u magnus-buttons -S -120s --no-pager" | grep -E "R1 → play|→ play"; then
        printf '\nPASS — the daemon saw the press and played the welcome file.\n'
    else
        printf '\nFAIL — no play event in the service log. Debug (exact commands):\n'
        printf '  ssh %s "sudo systemctl stop magnus-buttons"\n' "$PC2"
        printf '  ssh -t %s "cd magnus && ./venv/bin/python magnus-g1/examples/button_trigger.py %s --debug"\n' "$PC2" "$IFACE"
        printf '  (press RB — --debug prints every key change; Ctrl-C, then: sudo systemctl start magnus-buttons)\n'
        exit 1
    fi
fi

printf '\nDeployed. Ops:\n'
printf '  logs:    ssh %s "sudo journalctl -u magnus-buttons -f"\n' "$PC2"
printf '  rebind:  edit routines/buttons.json on the robot — hot-reloads in ~1s\n'
printf '           (on-site edits are TEMPORARY: commit to git or the next deploy overwrites)\n'
printf '  voices:  NEW line: scripts/build_voices.sh · CHANGED line: scripts/build_voices.sh --force <name.wav>\n'
printf '           (existing files are skipped without --force!) then re-run this script\n'
