#!/usr/bin/env bash
# Turns full-resolution originals into the WebP files the site actually serves.
#
# Originals live in source-photos/ and are never deployed. Everything under
# public/Assets/ is generated from them by this script, which is why the shipped
# folder is a couple of megabytes instead of ninety.
#
# Usage:  bash tools/optimize-images.sh
# Needs:  ffmpeg on PATH
set -euo pipefail

cd "$(dirname "$0")/.."
SRC=source-photos
OUT=public/Assets

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found on PATH" >&2
  exit 1
fi

# convert <input> <output> <quality> <max-width>
convert() {
  ffmpeg -hide_banner -loglevel error -y -i "$1" \
    -vf "scale='min($4,iw)':-2:flags=lanczos" \
    -c:v libwebp -quality "$3" -compression_level 6 "$2"
  printf '  %s\n' "$2"
}

# Gallery photos ship at two widths and the page picks one with srcset:
# -800 fills the grid, -1600 covers high-DPR screens.
echo "Gallery"
mkdir -p "$OUT/Gallery"
for f in "$SRC"/Gallery/PHOTO*.*; do
  [ -e "$f" ] || continue
  n=$(basename "$f"); n=${n%.*}
  ffmpeg -hide_banner -loglevel error -y -i "$f" \
    -vf "scale='if(gt(iw,ih),1600,-2)':'if(gt(iw,ih),-2,1600)':flags=lanczos" \
    -c:v libwebp -quality 80 -compression_level 6 "$OUT/Gallery/$n-1600.webp"
  ffmpeg -hide_banner -loglevel error -y -i "$f" \
    -vf "scale='if(gt(iw,ih),800,-2)':'if(gt(iw,ih),-2,800)':flags=lanczos" \
    -c:v libwebp -quality 78 -compression_level 6 "$OUT/Gallery/$n-800.webp"
  printf '  %s -800 / -1600\n' "$n"
done

echo "Hero slideshow"
mkdir -p "$OUT/Slideshow"
for f in "$SRC"/Slideshow/*.*; do
  [ -e "$f" ] || continue
  n=$(basename "$f"); convert "$f" "$OUT/Slideshow/${n%.*}.webp" 85 900
done

echo "Logos, icons, project thumbnails"
for f in "$SRC"/*.png "$SRC"/*.jpg; do
  [ -e "$f" ] || continue
  n=$(basename "$f"); convert "$f" "$OUT/${n%.*}.webp" 88 700
done

echo "Case-study images"
for d in Drone VTOL EMGHand ESP32Drone; do
  [ -d "$SRC/$d" ] || continue
  mkdir -p "$OUT/$d"
  for f in "$SRC/$d"/*.*; do
    [ -e "$f" ] || continue
    n=$(basename "$f"); convert "$f" "$OUT/$d/${n%.*}.webp" 84 1400
  done
done

# Two case-study photos double as project-card thumbnails, where they render at
# roughly a third of the size. They get their own smaller copy so the card does
# not pull down a modal-sized photo.
echo "Project-card thumbnails"
convert "$SRC/EMGHand/full.jpg" "$OUT/EMGHand/full-card.webp" 72 700
convert "$SRC/ESP32Drone/gyro_accel_circuit.jpg" "$OUT/ESP32Drone/gyro_accel_circuit-card.webp" 72 700

# Tab icon, cut down from the full-size mark.
echo "Favicons"
ffmpeg -hide_banner -loglevel error -y -i "$OUT/SitePhoto.png"   -vf "pad=279:279:0:15:color=0x00000000,scale=64:64:flags=lanczos" -c:v png "$OUT/favicon-64.png"
ffmpeg -hide_banner -loglevel error -y -i "$OUT/SitePhoto.png"   -vf "pad=279:279:0:15:color=0x00000000,scale=180:180:flags=lanczos" -c:v png "$OUT/apple-touch-icon.png"
printf '  %s
  %s
' "$OUT/favicon-64.png" "$OUT/apple-touch-icon.png"

# The clips play muted in a modal at a few hundred pixels wide, so they are
# re-encoded down to that and stripped of audio. faststart puts the index at
# the front of the file so playback can begin before the download finishes.
echo "Video"
for f in "$SRC"/*/*.mp4; do
  [ -e "$f" ] || continue
  d=$(basename "$(dirname "$f")"); n=$(basename "$f")
  mkdir -p "$OUT/$d"
  ffmpeg -hide_banner -loglevel error -y -i "$f"     -vf "scale='min(854,iw)':-2:flags=lanczos"     -c:v libx264 -crf 27 -preset slow -profile:v main -pix_fmt yuv420p     -movflags +faststart -an "$OUT/$d/$n"
  printf '  %s
' "$OUT/$d/$n"
done

echo
echo "Done. public/Assets is now $(du -sh "$OUT" | cut -f1)."
