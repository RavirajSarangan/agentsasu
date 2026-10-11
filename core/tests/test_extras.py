import datetime as dt
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core import extras
from sasu_core.tools.runtime import Proc
from tests.conftest import TOKEN


@pytest.mark.parametrize(
    ("text", "typed"),
    [
        ("type this: see you at 5", "see you at 5"),
        ("Sasu, type pannu vanakkam nanba", "vanakkam nanba"),
        ("டைப் பண்ணு: நாளை சந்திப்போம்", "நாளை சந்திப்போம்"),
        ("what type of file is this", None),
    ],
)
def test_parse_type(text: str, typed: str | None) -> None:
    assert extras.parse_type(text) == typed


@pytest.mark.parametrize(
    ("text", "ok"),
    [("read this", True), ("padichu sollu", True), ("read this book about Rome later", False)],
)
def test_read_intent(text: str, ok: bool) -> None:
    assert extras.is_read(text) is ok


def test_festivals() -> None:
    assert extras.festival(dt.date(2027, 1, 14))[0] == "pongal"  # type: ignore[index]
    assert extras.festival(dt.date(2026, 11, 8))[0] == "deepavali"  # type: ignore[index]
    assert extras.festival(dt.date(2026, 10, 11)) is None


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


class Clip:
    """Fake Mac: a clipboard, a selection and a front app."""

    def __init__(self) -> None:
        self.board = "my old clipboard"
        self.selection = "இன்று மழை வரும்."
        self.calls: list[list[str]] = []

    async def __call__(self, args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        self.calls.append(list(args))
        joined = " ".join(args)
        if args == ["pbpaste"]:
            return Proc(0, self.board, "")
        if args == ["pbcopy"]:
            self.board = stdin or ""
            return Proc(0, "", "")
        if 'keystroke "c"' in joined:
            self.board = self.selection
        if "frontmost" in joined:
            return Proc(0, "Notes", "")
        return Proc(0, "", "")


def test_voice_typing_asks_first_and_restores_clipboard(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = clip = Clip()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "type this: நாளை சந்திப்போம்"}))
        ask = until(ws, "confirm_request")[-1]
        ws.send_text(json.dumps({"type": "confirm_response", "id": ask["id"], "approved": True}))
        assert until(ws, "turn_done")[-1]["ok"] is True
    pasted = [c for c in clip.calls if 'keystroke "v"' in " ".join(c)]
    assert pasted and clip.board == "my old clipboard"


def test_read_aloud_speaks_the_selection_in_tamil(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = clip = Clip()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "read this"}))
        events = until(ws, "turn_done")
    start = next(e for e in events if e["type"] == "say_start")
    assert start["lang"] == "ta"
    assert clip.board == "my old clipboard"
