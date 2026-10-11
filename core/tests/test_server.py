import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sasu_core.demo import detect_lang
from sasu_core.protocol import (
    ControlAuthResult,
    ControlLock,
    ControlUnlock,
    core_event_adapter,
    json_schema,
)
from tests.conftest import TOKEN

WS = f"/ws?t={TOKEN}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    seen = []
    while True:
        event = json.loads(ws.receive_text())
        core_event_adapter.validate_python(event)
        seen.append(event)
        if event["type"] == kind:
            return seen


def test_health_reveals_nothing(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_security_api_needs_token(client: TestClient) -> None:
    assert client.get("/api/security").status_code == 401
    assert client.get("/api/security", headers={"Authorization": "Bearer nope"}).status_code == 401
    body = client.get("/api/security", headers=AUTH).json()
    assert body["audit"]["ok"] is True and body["bind"] == "127.0.0.1"


def test_no_api_docs(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_ws_rejects_bad_token_and_audits_it(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?t=nope") as ws:
        ws.receive_text()
    kinds = [
        (e["kind"], e["data"].get("reason")) for e in client.get("/api/audit", headers=AUTH).json()
    ]
    assert ("rejected", "bad_token") in kinds


def test_ws_rejects_foreign_origin(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(WS, headers={"origin": "https://evil.example"}) as ws,
    ):
        ws.receive_text()


def test_ws_accepts_app_origin(client: TestClient) -> None:
    with client.websocket_connect(WS, headers={"origin": "tauri://localhost"}) as ws:
        assert json.loads(ws.receive_text())["type"] == "ready"


def test_text_command_runs_a_full_turn(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "ஹலோ சாசு"}))
        events = until(ws, "turn_done")
    types = [e["type"] for e in events]
    assert types[:2] == ["wake", "listening"]
    assert {"thinking", "tool_start", "tool_end", "say_start", "say_chunk", "say_end"} <= set(types)
    assert next(e for e in events if e["type"] == "transcript")["lang"] == "ta"
    assert events[-1]["ok"] is True


def test_confirm_then_touch_id_for_dangerous(client: TestClient) -> None:
    core = client.app.state.core  # type: ignore[attr-defined]
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "Empty the trash"}))
        confirm = until(ws, "confirm_request")[-1]
        assert confirm["risk"] == "dangerous"
        ws.send_text(
            json.dumps({"type": "confirm_response", "id": confirm["id"], "approved": True})
        )
        auth = until(ws, "auth_required")[-1]
        # A WebSocket client cannot answer Touch ID: only the shell's stdin channel can.
        ws.send_text(json.dumps({"type": "confirm_response", "id": auth["id"], "approved": True}))
        client.portal.call(core.control, ControlAuthResult(id=auth["id"], ok=True))  # type: ignore[union-attr]
        assert until(ws, "turn_done")[-1]["ok"] is True


def test_denied_confirmation_runs_nothing(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "delete old screenshots"}))
        confirm = until(ws, "confirm_request")[-1]
        ws.send_text(
            json.dumps({"type": "confirm_response", "id": confirm["id"], "approved": False})
        )
        events = until(ws, "turn_done")
    assert events[-1]["ok"] is False
    assert not any(e["type"] == "tool_start" and e["name"] == "files.trash" for e in events)


def test_lock_blocks_commands_until_shell_unlocks(client: TestClient) -> None:
    core = client.app.state.core  # type: ignore[attr-defined]
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        client.portal.call(core.control, ControlLock(reason="screen"))  # type: ignore[union-attr]
        assert until(ws, "locked")[-1]["reasons"] == ["screen"]
        ws.send_text(json.dumps({"type": "text_command", "text": "open Safari"}))
        assert until(ws, "error")[-1]["code"] == "locked"
        client.portal.call(core.control, ControlUnlock(reason="screen"))  # type: ignore[union-attr]
        until(ws, "unlocked")
        ws.send_text(json.dumps({"type": "text_command", "text": "open Safari"}))
        assert until(ws, "turn_done")[-1]["ok"] is True


def test_stranger_is_rejected(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "stranger: open mail"}))
        events = until(ws, "turn_done")
    assert any(e["type"] == "speaker_rejected" for e in events)
    assert not any(e["type"] == "tool_start" for e in events)


def test_bad_command_returns_error_event(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "launch_missiles"}))
        assert json.loads(ws.receive_text())["code"] == "bad_command"


def test_rate_limit(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        for _ in range(40):
            ws.send_text(json.dumps({"type": "ptt_stop"}))
        assert until(ws, "error")[-1]["code"] == "rate_limited"


def test_without_a_key_sasu_asks_for_one(bare_client: TestClient) -> None:
    with bare_client.websocket_connect(WS) as ws:
        status = until(ws, "brain_status")[-1]
        assert status["ready"] is False
        ws.send_text(json.dumps({"type": "text_command", "text": "write a poem about rain"}))
        assert until(ws, "error")[-1]["code"] == "no_brain"


def test_key_over_stdin_makes_brain_ready(bare_client: TestClient) -> None:
    from sasu_core.protocol import ControlSecret

    core = bare_client.app.state.core  # type: ignore[attr-defined]
    with bare_client.websocket_connect(WS) as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.control, ControlSecret(provider="gemini", key="k" * 39))  # type: ignore[union-attr]
        status = until(ws, "brain_status")[-1]
        assert status["ready"] is True and status["keys"] == ["gemini"]
    # the key never shows up in the audit log
    assert "kkkk" not in json.dumps(bare_client.get("/api/audit", headers=AUTH).json())


def test_detect_lang() -> None:
    assert detect_lang("open Safari") == "en"
    assert detect_lang("சஃபாரி திற") == "ta"


def test_schema_lists_every_event() -> None:
    names = set(json_schema()["coreEvent"]["discriminator"]["mapping"])
    assert {
        "ready",
        "auth_required",
        "speaker_rejected",
        "locked",
        "plan_preview",
        "undo_available",
    } <= names
