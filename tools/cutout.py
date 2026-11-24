"""Cuts a CAD render or product-style photo out of a plain light background.

Usage:  python tools/cutout.py in.png out.webp [max-width] [tolerance]

Flood-fills inward from every border pixel, stepping between neighbours that
differ by less than `tolerance` (default 6, on 0-255), so it follows soft
gradients and vignettes but stops at the part's outline. The filled region
becomes transparent, with a one-pixel feather so the edge doesn't look cut
with scissors. Works for renders and photos shot on a seamless background,
not for busy scenes. Needs opencv-python, numpy and Pillow.
"""
import sys

import cv2
import numpy as np
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
max_w = int(sys.argv[3]) if len(sys.argv) > 3 else 1200
tol = int(sys.argv[4]) if len(sys.argv) > 4 else 6

rgb = np.array(Image.open(src).convert("RGB"))
h, w = rgb.shape[:2]
mask = np.zeros((h + 2, w + 2), np.uint8)
flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
img = cv2.GaussianBlur(rgb, (3, 3), 0)
for x in range(0, w, 8):
    for y in (0, h - 1):
        if not mask[y + 1, x + 1]:
            cv2.floodFill(img, mask, (x, y), 0, (tol,) * 3, (tol,) * 3, flags)
for y in range(0, h, 8):
    for x in (0, w - 1):
        if not mask[y + 1, x + 1]:
            cv2.floodFill(img, mask, (x, y), 0, (tol,) * 3, (tol,) * 3, flags)

background = mask[1:-1, 1:-1] > 0
# Close pinholes in the part, then soften the outline by a pixel.
part = cv2.morphologyEx((~background).astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
alpha = cv2.GaussianBlur(cv2.erode(part, np.ones((2, 2), np.uint8)), (3, 3), 0)

im = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
if im.width > max_w:
    im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
im.save(out, quality=86, method=6)
print(f"{out}: {im.width}x{im.height}")
