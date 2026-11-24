#!/usr/bin/env bash
# Turns full-resolution originals into the WebP and MP4 files the site serves.
#
# Originals live in source-photos/ and are never deployed. Everything under
# public/Assets/ is generated from them by this script, which is why the shipped
# folder is a few megabytes instead of ninety.
#
# Outputs that are already newer than their source are skipped, so re-running
# only touches what changed (and doesn't churn every file in git). FORCE=1
# rebuilds everything.
#
# Usage:  bash tools/optimize-images.sh          FORCE=1 bash tools/optimize-images.sh
# Needs:  ffmpeg on PATH
set -euo pipefail

cd "$(dirname "$0")/.."
SRC=source-photos
OUT=public/Assets

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found on PATH" >&2
  exit 1
fi

ff() { ffmpeg -hide_banner -loglevel error -y "$@"; }

# fresh <src> <out>: true when <out> exists, is newer than <src>, and FORCE is unset
fresh() { [ -z "${FORCE:-}" ] && [ -e "$2" ] && [ "$2" -nt "$1" ]; }

# webp <input> <output> <quality> <max-width> [ffmpeg input options...]
webp() {
  local in="$1" out="$2" q="$3" w="$4"; shift 4
  fresh "$in" "$out" && return
  ff "$@" -i "$in" -frames:v 1 -vf "scale='min($w,iw)':-2:flags=lanczos" \
    -c:v libwebp -quality "$q" -compression_level 6 "$out"
  printf '  %s\n' "$out"
}

# card <input> <output> [ffmpeg input options...]
# Centre-cropped to 4:3 and 900 px wide.
card() {
  local in="$1" out="$2"; shift 2
  fresh "$in" "$out" && return
  ff "$@" -i "$in" -frames:v 1 \
    -vf "crop='min(iw,ih*4/3)':'min(ih,iw*3/4)',scale=900:-2:flags=lanczos" \
    -c:v libwebp -quality 80 -compression_level 6 "$out"
  printf '  %s\n' "$out"
}

# Gallery photos ship at two sizes and the page picks one with srcset: -800
# fills the grid, -1600 covers high-DPR screens. Both are capped on the long
# edge so portrait and landscape shots come out the same weight.
echo "Gallery"
mkdir -p "$OUT/Gallery"
for f in "$SRC"/Gallery/PHOTO*.*; do
  [ -e "$f" ] || continue
  n=$(basename "$f"); n=${n%.*}
  for size in "1600 80" "800 78"; do
    set -- $size
    out="$OUT/Gallery/$n-$1.webp"
    fresh "$f" "$out" && continue
    ff -i "$f" -vf "scale=$1:$1:force_original_aspect_ratio=decrease:flags=lanczos" \
      -c:v libwebp -quality "$2" -compression_level 6 "$out"
    printf '  %s\n' "$out"
  done
done

# 4:3 crops of two photos that appear at thumbnail size on their project pages.
echo "4:3 crops"
mkdir -p "$OUT/Cards"
card "$SRC/VTOL/dropper.png"                  "$OUT/Cards/vtol.webp"
card "$SRC/ESP32Drone/gyro_accel_circuit.jpg" "$OUT/Cards/esp32.webp"

echo "Case-study images"
webp "$SRC/image-dronev1.png" "$OUT/image-dronev1.webp" 88 700
# Portfolio/ holds figures and photos cut out of the portfolio PDF pages.
for d in Drone VTOL EMGHand ESP32Drone Portfolio; do
  [ -d "$SRC/$d" ] || continue
  mkdir -p "$OUT/$d"
  for f in "$SRC/$d"/*.png "$SRC/$d"/*.jpg; do
    [ -e "$f" ] || continue
    n=$(basename "$f"); webp "$f" "$OUT/$d/${n%.*}.webp" 84 1600
  done
done

# Tab icons: the CK mark centred on a transparent square, then scaled.
echo "Favicons"
for size in 64 180; do
  out="$OUT/favicon-$size.png"; [ "$size" = 180 ] && out="$OUT/apple-touch-icon.png"
  fresh "$SRC/SitePhoto.png" "$out" && continue
  ff -i "$SRC/SitePhoto.png" \
    -vf "pad='max(iw,ih)':'max(iw,ih)':'(ow-iw)/2':'(oh-ih)/2':color=0x00000000,scale=$size:$size:flags=lanczos" \
    -c:v png "$out"
  printf '  %s\n' "$out"
done

# The clips play muted inline at a few hundred pixels wide, so they are
# re-encoded down to 640 px and stripped of audio. faststart puts the index at
# the front of the file so playback can begin before the download finishes.
# Black letterbox bars (the VTOL clips were filmed in portrait around landscape
# action) are found with cropdetect and cut off. Each clip also gets a poster
# frame, taken from the finished encode, so the page isn't blank before it plays.
# The page's width/height attributes should match the printed size.
echo "Video"
for f in "$SRC"/*/*.mp4; do
  [ -e "$f" ] || continue
  d=$(basename "$(dirname "$f")"); n=$(basename "$f" .mp4)
  out="$OUT/$d/$n.mp4"
  mkdir -p "$OUT/$d"
  if ! fresh "$f" "$out"; then
    crop=$(ffmpeg -hide_banner -i "$f" -vf cropdetect=limit=24:round=2 -f null - 2>&1 \
             | grep -o 'crop=[0-9:]*' | sort | uniq -c | sort -rn | awk 'NR==1 {print $2}')
    ff -i "$f" -vf "${crop:+$crop,}scale='min(640,iw)':-2:flags=lanczos" \
      -c:v libx264 -crf 28 -preset slow -profile:v main -pix_fmt yuv420p \
      -movflags +faststart -an "$out"
    ff -ss 1 -i "$out" -frames:v 1 -c:v libwebp -quality 75 "$OUT/$d/$n-poster.webp"
    size=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$out")
    printf '  %s (%s, + poster)\n' "$out" "$size"
  fi
done

echo
echo "Done. public/Assets is now $(du -sh "$OUT" | cut -f1)."
