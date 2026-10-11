import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core.fastpath import battery_reply, parse
from tests.conftest import TOKEN


@pytest.mark.parametrize(
    ("text", "tool", "args"),
    [
        # English
        ("Hey Sasu, play some music", "media_control", {"action": "play"}),
        ("next song", "media_control", {"action": "next"}),
        ("pause the music", "media_control", {"action": "pause"}),
        ("volume 30", "system_volume", {"level": 30}),
        ("set the volume to 75 percent", "system_volume", {"level": 75}),
        ("turn it down", "system_volume_step", {"delta": -15}),
        ("open Safari", "apps_open", {"app": "Safari"}),
        ("open vs code", "apps_open", {"app": "Visual Studio Code"}),
        ("open youtube", "web_open", {"url": "youtube.com"}),
        ("dark mode on", "system_dark_mode", {"on": True}),
        ("light mode", "system_dark_mode", {"on": False}),
        # Tanglish
        ("paattu podu", "media_control", {"action": "play"}),
        ("next podu", "media_control", {"action": "next"}),
        ("sound konjam kammi pannu", "system_volume_step", {"delta": -15}),
        ("Safari open pannu", "apps_open", {"app": "Safari"}),
        ("google open pannu", "web_open", {"url": "google.com"}),
        # Tamil
        ("சாசு, பாட்டு போடு", "media_control", {"action": "play"}),
        ("அடுத்த பாட்டு", "media_control", {"action": "next"}),
        ("சத்தம் ௫௦", "system_volume", {"level": 50}),
        ("சத்தம் குறை", "system_volume_step", {"delta": -15}),
    ],
)
def test_parses_common_requests(text: str, tool: str, args: dict[str, Any]) -> None:
    fast = parse(text)
    assert fast is not None, text
    assert fast.calls == [(tool, args)]


@pytest.mark.parametrize("text", ["what's the time?", "மணி என்ன", "mani enna"])
def test_time_needs_no_tools(text: str) -> None:
    fast = parse(text)
    assert fast is not None and fast.kind == "time" and fast.calls == []
    assert "மணி" in fast.say_ta


@pytest.mark.parametrize(
    "text",
    [
        "write a poem about rain",
        "open the file I downloaded yesterday and summarise it",
        "Downloads la irukura PDF ellam oru folder-la podu",
        "delete my old screenshots",
        "what's the weather in Chennai tomorrow and should I take an umbrella",
    ],
)
def test_leaves_real_questions_to_the_ai(text: str) -> None:
    assert parse(text) is None


def test_battery_reply_in_both_languages() -> None:
    content = "OK: System info\nBattery: 82% (charging)"
    assert battery_reply(content, "en") == "Battery is at 82 percent, charging."
    assert battery_reply(content, "ta").startswith("Battery 82")


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def test_fast_turn_runs_without_an_ai_key_and_answers_in_tamil(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "சத்தம் 40"}))
        events = until(ws, "turn_done")
    kinds = [e["type"] for e in events]
    assert "tool_start" in kinds and "undo_available" in kinds and events[-1]["ok"] is True
    said = "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))
    assert said == "சத்தம் 40."
    assert any(c[-1] == "40" for c in core.runner.calls)  # ran through the (fake) runner


def test_guest_can_play_music_but_not_open_apps(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(_guest, core, "open Terminal")  # type: ignore[union-attr]
        events = until(ws, "turn_done")
    said = "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))
    assert "only my owner" in said
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(_guest, core, "play some music")  # type: ignore[union-attr]
        assert until(ws, "turn_done")[-1]["ok"] is True


async def _guest(core: Any, text: str) -> None:
    core.start_text_turn(text, guest=True)


@pytest.mark.parametrize(
    ("text", "delta"),
    [("Satam kurey", -15), ("satham konjam kammi", -15), ("சதம் க", -15), ("saththam kootu", 15)],
)
def test_tamil_spellings_whisper_produces(text: str, delta: int) -> None:
    fast = parse(text)
    assert fast is not None and fast.calls == [("system_volume_step", {"delta": delta})]
