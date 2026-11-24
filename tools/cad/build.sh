#!/usr/bin/env bash
# Builds the CAD imagery on the home page and project pages:
#   - public/Assets/Models/quadcopter.glb, the live 3D model in the home hero
#   - public/Assets/Cutouts/*.webp, transparent renders and cut-out photos
#
# STL exports live in source-photos/CAD/; the cut-out photos and renders come
# from source-photos/. Re-run after re-exporting a part from SolidWorks.
#
# Usage:  bash tools/cad/build.sh
# Needs:  python with numpy, opencv-python, Pillow and playwright; Edge or Chrome
set -euo pipefail

cd "$(dirname "$0")/../.."
SRC=source-photos
OUT=public/Assets
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT/Models" "$OUT/Cutouts"

py() { python -I "$@"; }

echo "Models"
py tools/stl2glb.py "$OUT/Models/quadcopter.glb" --two-tone=50 --edges "$SRC/CAD/hsd-airframe.stl"
py tools/stl2glb.py "$TMP/esp32.glb" --edges "$SRC/CAD/esp32-frame.stl"
# The two finger links, laid end to end along their length with a small gap.
py tools/stl2glb.py "$TMP/finger.glb" --edges "$SRC/CAD/finger-middle.stl" "$SRC/CAD/finger-end.stl@0,0,54"

echo "Renders"
py tools/cad/render.py "$OUT/Models/quadcopter.glb" "$OUT/Cutouts/quadcopter.webp" "-55deg 70deg auto" 1400
py tools/cad/render.py "$TMP/esp32.glb"  "$OUT/Cutouts/esp32-frame.webp" "-35deg 60deg auto" 900
py tools/cad/render.py "$TMP/finger.glb" "$OUT/Cutouts/finger.webp"      "-50deg 62deg auto" 900

echo "Cut-outs"
py tools/cutout.py "$SRC/Portfolio/pickup-assembly.png" "$OUT/Cutouts/pickup-assembly.webp" 900
py tools/cutout.py "$SRC/VTOL/ldgcad.png"               "$OUT/Cutouts/leg-bracket.webp"     700
py tools/cutout.py "$SRC/Portfolio/plate-underside.png" "$OUT/Cutouts/plate-underside.webp" 700
py tools/cutout.py "$SRC/Portfolio/hammer.png"          "$OUT/Cutouts/hammer.webp"          600 3
