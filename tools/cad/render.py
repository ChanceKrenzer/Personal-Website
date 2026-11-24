"""Renders GLBs to transparent WebP images through <model-viewer>, so the
static images on the site are lit and edged exactly like the live 3D viewer.

Usage:  python tools/cad/render.py model.glb out.webp "<theta> <phi> auto" [width]

Runs headless Edge (or Chrome via BROWSER) through Playwright against a
throwaway local server, at 2x pixel density, then trims the empty margin.
Needs: playwright, Pillow, and a network connection for the model-viewer script.
"""
import functools
import http.server
import io
import os
import pathlib
import sys
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

BROWSER = os.environ.get("BROWSER", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
glb, out, orbit = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
width = int(sys.argv[4]) if len(sys.argv) > 4 else 1200
here = pathlib.Path(__file__).parent.resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        return str(glb) if path.startswith("/model.glb") else str(here / "stage.html")

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/stage.html?src=/model.glb&orbit={orbit.replace(' ', '%20')}"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=BROWSER, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 900, "height": 700}, device_scale_factor=2)
    page.goto(url)
    page.wait_for_selector("body[data-ready]", timeout=60000)
    page.wait_for_timeout(500)
    png = page.screenshot(omit_background=True)
    browser.close()
server.shutdown()

im = Image.open(io.BytesIO(png)).convert("RGBA")
im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 4 else 0).getbbox())
if im.width > width:
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
im.save(out, quality=88, method=6)
print(f"{out}: {im.width}x{im.height}")
