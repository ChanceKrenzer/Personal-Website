"""Renders the link-preview images in public/Assets/og/ from card.html.

Each card is screenshotted through Playwright and saved as a JPEG of under
100 KB, since some scrapers (WhatsApp in particular) skip preview images that
are much larger. Run tools/cad/build.sh first, since the cards use its renders.

Usage:  python tools/og/render.py
Needs:  playwright and Pillow; Microsoft Edge, or Chrome via BROWSER
"""
import io
import os
import pathlib
import urllib.parse

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "public" / "Assets" / "og"
CARD = (ROOT / "tools" / "og" / "card.html").as_uri()
BROWSER = os.environ.get("BROWSER", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# name: (title, sub, picture relative to public/Assets)
CARDS = {
    "home": ("Chance Krenzer", "Mechanical and aerospace engineering, Case Western Reserve University",
             "Cutouts/quadcopter.webp"),
    "quadcopter": ("High-Speed Quadcopter", "A 3D printed airframe designed for a 500 km/h pass",
                   "Cutouts/quadcopter.webp"),
    "vtol": ("VTOL Payload and Landing Gear", "3rd of 20 teams at the 2026 championship",
             "Cutouts/pickup-assembly.webp"),
    "esp32-quadcopter": ("ESP32 Quadcopter", "Built from scratch for about $60 in parts",
                         "Cutouts/esp32-frame.webp"),
    "emg-hand": ("EMG Robotic Hand", "Opens and closes on a muscle signal, built in two days",
                 "Cutouts/finger.webp"),
    "shop": ("Making the Parts", "Lathe, mill, waterjet and jigs", "Cutouts/hammer.webp"),
}

OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=BROWSER)
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    for name, (title, sub, img) in CARDS.items():
        query = urllib.parse.urlencode({"title": title, "sub": sub, "img": f"../../public/Assets/{img}"})
        page.goto(f"{CARD}?{query}")
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        shot.save(OUT / f"{name}.jpg", quality=86, optimize=True)
        print(f"  {OUT.relative_to(ROOT) / (name + '.jpg')}")
    browser.close()
