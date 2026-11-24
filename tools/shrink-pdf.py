"""Makes the web copy of the portfolio PDF.

Every page of the exported portfolio is a 3840 x 2160 image, which puts the
file at about 8.5 MB. This re-encodes those images at 2400 px and JPEG
quality 82 (about 4 MB, still sharp at full-screen) and keeps the text layer,
so the PDF stays searchable and its text can still be copied.

Usage:  python tools/shrink-pdf.py "<exported portfolio>.pdf" public/Chance-Krenzer-Portfolio.pdf
Needs:  pypdf and Pillow
"""
import sys

from PIL import Image
from pypdf import PdfReader, PdfWriter

src, out = sys.argv[1], sys.argv[2]
writer = PdfWriter(clone_from=PdfReader(src))
for page in writer.pages:
    for image in page.images:
        img = image.image.convert("RGB")
        img.thumbnail((2400, 2400), Image.LANCZOS)
        image.replace(img, quality=82)
writer.compress_identical_objects()
with open(out, "wb") as f:
    writer.write(f)
