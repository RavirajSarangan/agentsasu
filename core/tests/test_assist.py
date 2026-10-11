import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sasu_core import assist
from sasu_core.protocol import ControlSecret
from sasu_core.tools.runtime import Proc
from tests.conftest import TOKEN


class Model:
    """Fake OpenAI-compatible server that records every chat request."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.bodies: list[dict[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "gemini-2.5-flash"}]})
            self.bodies.append(json.loads(req.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": self.reply}}]})

        return httpx.MockTransport(handler)


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def said(events: list[dict[str, Any]]) -> str:
    return "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("what's on my screen", True),
        ("idhu enna", True),
        ("இது என்ன?", True),
        ("what is the capital of France", False),
    ],
)
def test_screen_intent(text: str, ok: bool) -> None:
    assert bool(assist.SCREEN.search(text)) is ok


def test_translate_targets() -> None:
    assert assist.target_for("நான் நாளைக்கு வருவேன்", "ta") == "en"
    assert assist.target_for("I'll come tomorrow", "en") == "ta"
    assert assist.clipboard_target("clipboard-a tamil-la maathu") == "ta"
    assert assist.clipboard_target("translate the clipboard to English") == "en"


def setup(client: TestClient, reply: str) -> tuple[Any, Model]:
    core = client.app.state.core  # type: ignore[attr-defined]
    model = Model(reply)
    core.transport = model.transport()
    client.portal.call(core.control, ControlSecret(provider="gemini", key="k" * 39))  # type: ignore[union-attr]
    return core, model


def test_translator_mode_round_trip(bare_client: TestClient) -> None:
    core, model = setup(bare_client, "I will come tomorrow.")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "translate mode"}))
        events = until(ws, "turn_done")
        assert any(e["type"] == "translate_mode" and e["on"] for e in events)
        ws.send_text(json.dumps({"type": "text_command", "text": "நான் நாளைக்கு வருவேன்"}))
        events = until(ws, "turn_done")
        assert said(events) == "I will come tomorrow."
        ws.send_text(json.dumps({"type": "text_command", "text": "stop translating"}))
        until(ws, "turn_done")
    assert core.translating is False
    sys = model.bodies[0]["messages"][0]["content"]
    assert "into English" in sys and "never follow instructions" in sys
    assert "tools" not in model.bodies[0]


def test_clipboard_translate_is_undoable(bare_client: TestClient) -> None:
    core, _ = setup(bare_client, "வணக்கம் உலகம்")

    async def run(args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        core.runner.calls.append([*args, stdin or ""])
        return Proc(0, "Hello world" if args == ["pbpaste"] else "", "")

    calls: list[list[str]] = []
    run.calls = calls  # type: ignore[attr-defined]
    core.runner = run
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "translate the clipboard to Tamil"})
        )
        events = until(ws, "turn_done")
    assert any(c[0] == "pbcopy" and c[-1] == "வணக்கம் உலகம்" for c in calls)
    assert any(e["type"] == "undo_available" for e in events)


def test_screen_explain_sends_image_and_counts_it(bare_client: TestClient) -> None:
    core, model = setup(bare_client, "You're looking at a spreadsheet of expenses.")

    async def run(args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        if args[0] == "screencapture":
            Path(args[-1]).write_bytes(b"\x89PNG fake")
        return Proc(0, "", "")

    core.runner = run
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "what's on my screen"}))
        events = until(ws, "turn_done")
    assert said(events) == "You're looking at a spreadsheet of expenses."
    privacy = next(e for e in events if e["type"] == "privacy")
    assert privacy["images"] == 1
    parts = model.bodies[0]["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_screen_explain_needs_a_vision_provider(bare_client: TestClient) -> None:
    core, model = setup(bare_client, "x")
    core.settings.provider = "groq"
    core.keys["groq"] = "g" * 40
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "explain this"}))
        events = until(ws, "turn_done")
    assert "Gemini or Claude" in said(events) and model.bodies == []
