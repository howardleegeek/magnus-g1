#!/usr/bin/env bash
# Find out which PulseAudio sink your external speaker is on, and how loud it gets.
#
# Run ON the Jetson. It plays the welcome clip through every output in turn,
# announcing each one's number first, so you just listen for which number comes
# out of the speaker you plugged in — then put that sink in buttons.json:
#
#     "external_speaker": { "sink": "<substring>", "gain_pct": 150 }
#
#   usage: scripts/speaker_test.sh [gain_pct]   (default 150 = PulseAudio's max boost)
set -euo pipefail

GAIN="${1:-150}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIP="$REPO/voices/showroom_welcome.wav"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/1000/pulse/native}"

command -v paplay >/dev/null || { echo "paplay not installed" >&2; exit 1; }
[ -f "$CLIP" ] || { echo "missing $CLIP" >&2; exit 1; }

VOL=$((65536 * GAIN / 100))
mapfile -t SINKS < <(pactl list short sinks | cut -f2)
[ "${#SINKS[@]}" -gt 0 ] || { echo "no PulseAudio sinks" >&2; exit 1; }

echo "playing at ${GAIN}% through ${#SINKS[@]} output(s) — listen for the number"
for i in "${!SINKS[@]}"; do
    n=$((i + 1))
    echo "  [$n] ${SINKS[$i]}"
    # Unmute and max the sink itself first: a muted or turned-down sink makes a
    # working speaker look dead, which is the usual false alarm here.
    pactl set-sink-mute "${SINKS[$i]}" 0 2>/dev/null || true
    pactl set-sink-volume "${SINKS[$i]}" 100% 2>/dev/null || true
    paplay --device="${SINKS[$i]}" --volume="$VOL" "$CLIP" 2>/dev/null ||
        echo "      (failed — nothing connected to this output)"
done
echo "done — note which number you heard, then set it as \"sink\" in routines/buttons.json"
