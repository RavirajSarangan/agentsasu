"""Watch & tell: parsing, each watcher kind end to end, stop/list, API."""

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sasu_core import watch
from sasu_core.tools.runtime import Proc
from tests.conftest import TOKEN
from tests.test_bundle_h import Mac, said, until

FAST = {"download": 0.05, "file": 0.05, "battery": 0.05, "page": 0.05}


@pytest.mark.parametrize(
    ("text", "kind", "extra"),
    [
        ("download mudinja sollu", "download", None),
        ("tell me when the download is done", "download", None),
        ("100% aana sollu", "battery", 100),
        ("battery 80 percent aana sollu", "battery", 80),
        ("tell me when the battery reaches 20", "battery", 20),
        ("full charge aana sollu", "battery", 100),
        ("indha page-la price kuranja sollu", "page", True),
        ("indha page maarina sollu", "page", False),
        ("tell me when the price drops", "page", True),
        ("indha file maarina sollu", "file", None),
        ("run npm test and tell me when it's done", "command", "npm test"),
        ("`pnpm build` run panni mudinja sollu", "command", "pnpm build"),
    ],
)
def test_parse(text: str, kind: str, extra: Any) -> None:
    r = watch.parse(text)
    assert r is not None and r.kind == kind
    if kind == "battery":
        assert r.level == extra
    if kind == "page":
        assert r.price is extra
    if kind == "command":
        assert r.command == extra


@pytest.mark.parametrize("text", ["download the report", "what's the battery", "open this page"])
def test_not_a_watch(text: str) -> None:
    assert watch.parse(text) is None


def test_price_and_text_helpers() -> None:
    assert watch.first_price("Was ₹1,299.00 now") == 1299.0
    assert watch.first_price("£45 only") == 45.0
    assert watch.page_text("<p>Hi</p><script>evil()</script> <b>there</b>") == "Hi there"


class Box(Mac):
    """Fake Mac with a battery, a browser tab, a Finder selection and a shell."""

    def __init__(self) -> None:
        super().__init__()
        self.batt = 50
        self.front = "Safari"
        self.url = "https://shop.example/phone"
        self.selected = ""
        self.shell = Proc(0, "all good", "")

    async def __call__(self, args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        j = " ".join(args)
        if args[:2] == ["pmset", "-g"]:
            return Proc(
                0, f"Now drawing from 'AC Power'\n -InternalBattery-0\t{self.batt}%; charging", ""
            )
        if "frontmost is true" in j:
            return Proc(0, self.front, "")
        if "URL of current tab" in j:
            return Proc(0, self.url, "")
        if 'tell application "Finder" to set s to selection' in j:
            return Proc(0, self.selected, "")
        if args[:2] == ["/bin/zsh", "-c"]:
            self.calls.append([*args, str(timeout)])
            return self.shell
        return await super().__call__(args, timeout, stdin)


def setup(client: TestClient, tmp_path: Path) -> tuple[Any, Box]:
    core = client.app.state.core  # type: ignore[attr-defined]
    core.runner = box = Box()
    core.home = tmp_path
    core.watch_every = FAST
    return core, box


def fired(
    ws: Any, seen: list[dict[str, Any]] | None = None, approve: bool = False
) -> list[dict[str, Any]]:
    """Everything up to the announcement after a watch fires (answers confirms on the way)."""
    events = list(seen or [])
    done = any(e["type"] == "watch" and e["state"] == "fired" for e in events)
    while True:
        e = json.loads(ws.receive_text())
        events.append(e)
        if e["type"] == "confirm_request" and approve:
            ws.send_text(json.dumps({"type": "confirm_response", "id": e["id"], "approved": True}))
        elif e["type"] == "watch" and e["state"] == "fired":
            done = True
        elif e["type"] == "say_end" and done:
            return events


def test_download_watch(bare_client: TestClient, tmp_path: Path) -> None:
    core, box = setup(bare_client, tmp_path)
    dl = tmp_path / "Downloads"
    dl.mkdir()
    part = dl / "movie.mp4.crdownload"
    part.write_bytes(b"half")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "download mudinja sollu"}))
        started = until(ws, "watch")[-1]
        assert started["state"] == "started" and started["kind"] == "download"
        assert "movie.mp4" in started["label"]
        until(ws, "turn_done")
        part.rename(dl / "movie.mp4")
        events = fired(ws)
    assert "Your download finished: movie.mp4." in said(events)
    note = next(c for c in box.calls if any("display notification" in a for a in c))
    assert note[-2] == "Your download finished: movie.mp4."  # message travels in argv
    assert core.watches == {}


def test_download_watch_needs_a_download(bare_client: TestClient, tmp_path: Path) -> None:
    setup(bare_client, tmp_path)
    (tmp_path / "Downloads").mkdir()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "download mudinja sollu"}))
        events = until(ws, "turn_done")
    assert "don't see a download" in said(events) and events[-1]["ok"] is False


def test_battery_watch(bare_client: TestClient, tmp_path: Path) -> None:
    _, box = setup(bare_client, tmp_path)
    box.batt = 76
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "80% aana sollu"}))
        until(ws, "turn_done")
        box.batt = 80
        events = fired(ws)
    assert "Battery is at 80%." in said(events)


def test_page_price_drop(bare_client: TestClient, tmp_path: Path) -> None:
    core, box = setup(bare_client, tmp_path)
    prices = iter(["₹1,299", "₹1,299", "₹999"])

    def page(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=f"<html><h1>Phone</h1><span>{next(prices, '₹999')}</span></html>"
        )

    core.transport = httpx.MockTransport(page)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "indha page-la price kuranja sollu"})
        )
        seen = until(ws, "watch")
        assert seen[-1]["label"] == "price drop on shop.example"
        events = fired(ws, seen)
    assert "Price dropped from 1299 to 999." in said(events)


def test_page_watch_needs_a_browser(bare_client: TestClient, tmp_path: Path) -> None:
    _, box = setup(bare_client, tmp_path)
    box.front = "Finder"
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "indha page maarina sollu"}))
        events = until(ws, "turn_done")
    assert "Open the page in Safari or Chrome first." in said(events)


def test_command_watch_goes_through_policy(bare_client: TestClient, tmp_path: Path) -> None:
    _, box = setup(bare_client, tmp_path)
    box.shell = Proc(1, "", "FAIL src/app.test.ts\n2 tests failed")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "run npm test and tell me when it's done"})
        )
        events = fired(ws, approve=True)  # shell commands still ask first
        assert any(e["type"] == "confirm_request" for e in events)
    shell = next(c for c in box.calls if c[:2] == ["/bin/zsh", "-c"])
    assert shell[2] == "npm test" and shell[-1] == "3600.0"
    assert "“npm test” failed. 2 tests failed" in said(events)


def test_file_watch(bare_client: TestClient, tmp_path: Path) -> None:
    _, box = setup(bare_client, tmp_path)
    f = tmp_path / "notes.txt"
    f.write_text("v1")
    os.utime(f, (1_000_000, 1_000_000))
    box.selected = str(f)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "indha file maarina sollu"}))
        until(ws, "turn_done")
        f.write_text("v2")
        events = fired(ws)
    assert "notes.txt just changed." in said(events)


def test_list_stop_and_api(bare_client: TestClient, tmp_path: Path) -> None:
    core, box = setup(bare_client, tmp_path)
    core.watch_every = {**FAST, "battery": 60.0}
    box.batt = 40
    auth = {"Authorization": f"Bearer {TOKEN}"}
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        for level in (90, 95):
            ws.send_text(json.dumps({"type": "text_command", "text": f"{level}% aana sollu"}))
            until(ws, "turn_done")
        ws.send_text(json.dumps({"type": "text_command", "text": "what are you watching"}))
        assert "battery at 90%; battery at 95%" in said(until(ws, "turn_done"))
        rows = bare_client.get("/api/watch", headers=auth).json()
        assert [r["label"] for r in rows] == ["battery at 90%", "battery at 95%"]
        assert bare_client.delete(f"/api/watch/{rows[0]['id']}", headers=auth).json() == {
            "ok": True
        }
        ws.send_text(json.dumps({"type": "text_command", "text": "stop watching"}))
        assert "Stopped 1 watch." in said(until(ws, "turn_done"))
    assert core.watches == {}
    states = [e.data["state"] for e in reversed(core.audit.recent(20)) if e.kind == "watch"]
    assert states == ["started", "started", "stopped", "stopped"]
