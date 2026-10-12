"""Screenshots of the real app for the landing page (apps/web/public/shots/*.webp).

Runs a throwaway core on :8765 (temp data dir, fake runner, silent) seeded with sample
data, and drives the desktop UI from Vite on :1420 (the only dev origin the core trusts):

    pnpm --filter @sasu/desktop dev    # in one terminal
    uv run --project core --with playwright --with pillow python apps/web/scripts/render-shots.py
"""

from __future__ import annotations

import asyncio
import io
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from PIL import Image
from playwright.sync_api import Page, sync_playwright

from sasu_core import care
from sasu_core.protocol import (
    BrainStatus,
)
from sasu_core.server import create_app
from sasu_core.tools.runtime import Proc

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "apps/web/public/shots"
UI = "http://localhost:1420"
SEED = """localStorage.setItem("sasu.robot-settings", JSON.stringify({ onboarded: true, sosContact: "+44 7700 900123", sonName: "Raviraj", city: "Chennai" }));"""


async def fake_run(args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
    return Proc(0, "", "")


def start_core() -> tuple[Any, asyncio.AbstractEventLoop]:
    app = create_app("dev", data_dir=Path(tempfile.mkdtemp(prefix="sasu-shots-")), dev=True, delay=0.4)
    core = app.state.core
    core.runner = fake_run
    core.speaker.enabled = False
    core.settings.tts = False
    core.demo = True
    for fact in (
        "Amma's BP tablet is at 8 in the morning",
        "My Wi-Fi password is in the blue notebook",
        "Car service is due in March",
        "Ravi likes his coffee without sugar",
    ):
        core.memory.add(fact)
    for who, what, h, m in (("amma", "BP மாத்திரை", 8, 0), ("appa", "sugar tablet", 13, 30), ("amma", "vitamin D", 21, 0)):
        core.care_store.add(care.Dose(f"{h:02d}{m:02d}abcd"[:8], who, what, h, m))
    loop = asyncio.new_event_loop()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning", loop="none"))
    threading.Thread(target=lambda: loop.run_until_complete(server.serve()), daemon=True).start()
    time.sleep(1.5)
    return core, loop


def emit(core: Any, loop: asyncio.AbstractEventLoop, *events: Any) -> None:
    for e in events:
        asyncio.run_coroutine_threadsafe(core.hub.emit(e), loop).result()


def save(png: bytes, name: str, width: int) -> None:
    img = Image.open(io.BytesIO(png))
    img = img.convert("RGB")
    for suffix, w in (("", width), ("@2x", width * 2)):
        im = img if img.width <= w else img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
        path = OUT / f"{name}{suffix}.webp"
        im.save(path, "WEBP", quality=82, method=6)
        print(f"{path.name}: {im.width}x{im.height}, {path.stat().st_size // 1024} KB")


def panel(page: Page, route: str, settle: float = 1.2) -> bytes:
    page.goto(f"{UI}/#/panel{route}")
    time.sleep(settle)
    return page.screenshot()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    core, loop = start_core()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 1080, "height": 880}, device_scale_factor=2, color_scheme=scheme)
            ctx.add_init_script(SEED)
            page = ctx.new_page()
            page.goto(f"{UI}/#/panel")
            time.sleep(2)
            ready = BrainStatus(provider="gemini", model="gemini-2.5-flash", ready=True, keys=["gemini"], voice=False)
            emit(core, loop, ready)
            loop.call_soon_threadsafe(core.start_text_turn, "open Safari and search flights to Chennai")
            time.sleep(6)
            save(page.screenshot(), f"home-{scheme}", 1080)
            save(panel(page, "/memory"), f"memory-{scheme}", 1080)
            save(panel(page, "/security"), f"security-{scheme}", 1080)
            page.goto(f"{UI}/#/panel/settings")
            time.sleep(1.2)
            page.get_by_text("Amma mode", exact=True).first.scroll_into_view_if_needed()
            time.sleep(0.6)
            save(page.screenshot(), f"settings-{scheme}", 1080)
            page.close()

            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
