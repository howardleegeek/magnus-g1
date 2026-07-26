#!/usr/bin/env bash
# Re-master a voice WAV for showroom playback: as loud as possible without clipping.
#
# Why: TTS output lands around -25 LUFS with ~5 dB of unused headroom. In a room
# with people talking that is inaudible past a few metres. Broadcast/PA speech
# sits near -11 LUFS, so we compress the dynamic range (quiet syllables come up,
# loud ones stay put) and then normalise into the headroom we just freed.
#
#   usage: scripts/boost_loudness.sh voices/showroom_welcome.wav [target_LUFS]
#
# Writes <name>_loud.wav next to the source in the SAME format (rate/channels),
# so it stays a drop-in for whichever playback path already uses the original.
# Originals are never modified.
set -euo pipefail

SRC="${1:?usage: boost_loudness.sh <file.wav> [target_LUFS]}"
TARGET="${2:--11}"

[ -f "$SRC" ] || { echo "no such file: $SRC" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }

RATE=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate \
    -of default=nw=1:nk=1 "$SRC")
CH=$(ffprobe -v error -select_streams a:0 -show_entries stream=channels \
    -of default=nw=1:nk=1 "$SRC")
OUT="${SRC%.wav}_loud.wav"

# highpass  : drop sub-90 Hz rumble that eats headroom but is inaudible on small speakers
# acompressor: 3.5:1 above -18 dB — lifts quiet syllables, the main intelligibility win
# loudnorm  : land on the target integrated loudness, true peak capped at -1.5 dBTP
# alimiter  : hard safety net so nothing clips on a cheap amplifier
ffmpeg -hide_banner -loglevel error -y -i "$SRC" \
    -af "highpass=f=90,\
acompressor=threshold=-18dB:ratio=3.5:attack=5:release=150,\
loudnorm=I=${TARGET}:TP=-1.5:LRA=7,\
alimiter=limit=0.94" \
    -ar "$RATE" -ac "$CH" -sample_fmt s16 "$OUT"

echo "wrote $OUT  (${RATE} Hz, ${CH} ch)"
for f in "$SRC" "$OUT"; do
    printf '%-42s ' "$(basename "$f")"
    ffmpeg -hide_banner -i "$f" -af volumedetect -f null - 2>&1 |
        awk '/mean_volume/{m=$5} /max_volume/{p=$5} END{printf "mean %s dB  peak %s dB\n", m, p}'
done
