"""Render brand assets with headless Chrome: DMG background, OG image, favicons.

    pnpm --filter @sasu/web dev   # in one terminal
    uv run --with playwright --with pillow python apps/web/scripts/render-assets.py
"""

import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    for scale, name in ((1, "dmg-background.png"), (2, "dmg-background@2x.png")):
        pg = b.new_page(viewport={"width": 660, "height": 400}, device_scale_factor=scale)
        pg.goto(f"{BASE}/dmg.html")
        time.sleep(1.5)
        pg.screenshot(path=str(ROOT / "assets" / name))
    og = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    og.goto(f"{BASE}/og.html")
    time.sleep(2)
    og.screenshot(path=str(ROOT / "apps/web/public/og.png"))
    b.close()

icon = Image.open(ROOT / "assets/icon.png").convert("RGBA")
icon.resize((64, 64), Image.LANCZOS).save(ROOT / "apps/web/public/favicon.png")
icon.resize((180, 180), Image.LANCZOS).save(ROOT / "apps/web/public/apple-touch-icon.png")
print("assets rendered")
