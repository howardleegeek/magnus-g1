#!/usr/bin/env bash
# Build the voice pack from voices/lines.txt (name | text).
# Default engine: macOS `say`. Regenerate one file: build_voices.sh --force <name.wav>
# Requires: ffmpeg. Validates every generated file with examples/voice.py --check.
set -euo pipefail
cd "$(dirname "$0")/.."

VOICE="${SAY_VOICE:-Samantha}"
FORCE=""
ONLY=""
[ "${1:-}" = "--force" ] && { FORCE=1; ONLY="${2:-}"; }

fail=0
while IFS='|' read -r name text rate; do
    trim() { echo "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }
    name="$(trim "$name")"; text="$(trim "$text")"; rate="$(trim "${rate:-}")"
    [ -z "$name" ] || [ "${name:0:1}" = "#" ] && continue
    [ -n "$ONLY" ] && [ "$name" != "$ONLY" ] && continue
    out="voices/$name"
    if [ -f "$out" ] && [ -z "$FORCE" ]; then
        echo "skip (exists): $out"
    else
        tmp="$(mktemp /tmp/voice_XXXX).aiff"
        say -v "$VOICE" ${rate:+-r "$rate"} -o "$tmp" "$text"
        ffmpeg -y -loglevel error -i "$tmp" -ar 16000 -ac 1 -sample_fmt s16 "$out"
        rm -f "$tmp"
        echo "built: $out  (\"$text\")"
    fi
    python3 examples/voice.py --check "$out" || fail=1
done < voices/lines.txt

[ "$fail" = 0 ] && echo "voice pack OK" || { echo "voice pack has FAILURES"; exit 1; }
