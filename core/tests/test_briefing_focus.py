import asyncio
import json
import time
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sasu_core import briefing, focus
from sasu_core.protocol import FocusState
from tests.conftest import TOKEN


def test_compose_english_and_tamil() -> None:
    info = {
        "events": ["9:30 AM Standup", "2:00 PM Dentist"],
        "todos": ["Pay rent"],
        "battery": 22,
        "weather": {"city": "Chennai", "temp": 31, "code": 2, "max": 34, "rain": 40},
    }
    now = time.strptime("2026-10-12 08:05", "%Y-%m-%d %H:%M")
    en = briefing.compose(info, "en", "Raviraj", now)
    assert en.startswith("Good morning, Raviraj! It's 8:05 AM")
    assert "Chennai it's 31 degrees and partly cloudy" in en
    assert "2 events today. First up: 9:30 AM Standup." in en
    assert "Battery is at 22%" in en
    ta = briefing.compose(info, "ta", "", now)
    assert ta.startswith("காலை வணக்கம்!") and "Chennai-ல 31°" in ta


def test_weather_from_open_meteo() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "geocoding" in req.url.host:
            assert req.url.params["name"] == "Chennai"
            return httpx.Response(
                200, json={"results": [{"name": "Chennai", "latitude": 13.08, "longitude": 80.27}]}
            )
        return httpx.Response(
            200,
            json={
                "current": {"temperature_2m": 30.6, "weather_code": 61},
                "daily": {"temperature_2m_max": [33.2], "precipitation_probability_max": [70]},
            },
        )

    w = asyncio.run(briefing.weather("Chennai", httpx.MockTransport(handler)))
    assert w == {"city": "Chennai", "temp": 31, "code": 61, "max": 33, "rain": 70}
    assert asyncio.run(briefing.weather("", None)) is None


@pytest.mark.parametrize(
    ("text", "mins"),
    [
        ("focus 25 minutes", 25),
        ("focus mode", 25),
        ("45 nimisham focus", 45),
        ("focus for 90 mins", 90),
        ("கவனம்", 25),
    ],
)
def test_focus_parse(text: str, mins: int) -> None:
    assert focus.parse_start(text) == mins


def test_focus_not_triggered_by_other_text() -> None:
    assert focus.parse_start("stop focus") is None
    assert (
        focus.parse_start("can you help me focus on writing my thesis introduction today please")
        is None
    )
    assert focus.is_stop("Sasu stop focus")


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def test_briefing_turn_without_ai_key(bare_client: TestClient) -> None:
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "good morning"}))
        events = until(ws, "turn_done")
    said = "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))
    assert "It's" in said and events[-1]["ok"] is True
    assert any(e["type"] == "fun" and e["kind"] == "briefing" for e in events)


def test_focus_closes_apps_then_restores(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]

    async def fake(args: Any, timeout: float = 15, stdin: str | None = None) -> Any:
        from sasu_core.tools.runtime import Proc

        core.runner.calls.append(list(args))
        joined = " ".join(args)
        if "every process" in joined:
            return Proc(0, "Finder, Slack, Safari, WhatsApp", "")
        if "output volume of" in joined:
            return Proc(0, "60", "")
        if "is running" in joined:
            return Proc(0, "true", "")
        return Proc(0, "", "")

    core.runner.__call__ = fake  # type: ignore[method-assign]
    core.runner = fake
    core.runner.calls = []  # type: ignore[attr-defined]
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "focus 1 minute"}))
        events = until(ws, "turn_done")
        said = "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))
        assert "closed 2 distracting apps" in said
        quits = [c for c in core.runner.calls if any("quit" in a for a in c)]
        assert sorted(c[-1] for c in quits) == ["Slack", "WhatsApp"]
        assert until(ws, "focus")[-1]["remaining"] == 60
        ws.send_text(json.dumps({"type": "text_command", "text": "stop focus"}))
        until(ws, "turn_done")
    reopened = [c for c in core.runner.calls if c[:2] == ["open", "-a"]]
    assert sorted(c[-1] for c in reopened) == ["Slack", "WhatsApp"]
    assert core.runner.calls[-1][-1] == "60" or any(c[-1] == "60" for c in core.runner.calls)
    assert FocusState(remaining=0, total=0).type == "focus"
