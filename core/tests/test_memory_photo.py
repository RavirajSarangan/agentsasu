import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from sasu_core import memory as mem
from sasu_core.security.voiceprint import Profile, Voiceprint
from sasu_core.voice.pipeline import Heard
from tests.conftest import TOKEN

AUTH = {"Authorization": f"Bearer {TOKEN}"}
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 5000


@pytest.mark.parametrize(
    ("text", "fact"),
    [
        ("Remember that amma's birthday is June 3", "amma's birthday is June 3"),
        ("Sasu, remember my locker code is 4412", "my locker code is 4412"),
        ("amma birthday June 3 nu nyabagam vechukko", "amma birthday June 3"),
        ("அம்மா பிறந்தநாள் ஜூன் 3 நினைவில் வை", "அம்மா பிறந்தநாள் ஜூன் 3"),
        ("do you remember the song from yesterday", None),
    ],
)
def test_parse_save(text: str, fact: str | None) -> None:
    assert mem.parse_save(text) == fact


def test_memory_is_encrypted_and_searchable(tmp_path: Path) -> None:
    m = mem.Memory(tmp_path / "m.bin", AESGCM(b"k" * 32))
    m.add("Amma's birthday is June 3")
    m.add("The wifi password at office is on the fridge")
    assert b"Amma" not in (tmp_path / "m.bin").read_bytes()
    assert m.search("when is amma birthday")[0].text == "Amma's birthday is June 3"
    assert m.forget("amma birthday") == 1
    assert [f.text for f in m.all()] == ["The wifi password at office is on the fridge"]


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def said(events: list[dict[str, Any]]) -> str:
    return "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))


def test_remember_and_recall_by_voice(bare_client: TestClient) -> None:
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "remember amma's birthday is June 3"})
        )
        assert "I'll remember" in said(until(ws, "turn_done"))
        ws.send_text(
            json.dumps(
                {"type": "text_command", "text": "what did I tell you about amma's birthday"}
            )
        )
        assert "June 3" in said(until(ws, "turn_done"))
    assert (
        bare_client.get("/api/memory", headers=AUTH).json()[0]["text"]
        == "amma's birthday is June 3"
    )


def test_guest_cannot_save_or_read_memories(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.memory.add("bank pin is 1234")
    core.vault.upsert(
        Profile(
            "Raviraj",
            "owner",
            Voiceprint.enroll(
                [[1.0, 0.1, 0.0, 0.2], [0.9, 0.15, 0.05, 0.25], [1.1, 0.05, 0.0, 0.18]]
            ),
        )
    )
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        stranger = Heard("what did I tell you about the bank pin", "en", [0.0, 0.0, -1.0, 1.0], 2.0)
        bare_client.portal.call(core.voice_command, stranger)  # type: ignore[union-attr]
        events = until(ws, "turn_done")
    assert "1234" not in said(events)


def test_photo_upload_only_when_requested(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.settings.intruder_photo = True
    # unsolicited upload is refused
    assert (
        bare_client.post("/api/intruders?snap=nope", content=JPEG, headers=AUTH).status_code == 400
    )
    # no token, no upload
    assert bare_client.post("/api/intruders?snap=x", content=JPEG).status_code == 401
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.request_snap, "stranger")  # type: ignore[union-attr]
        req = until(ws, "snap_request")[-1]
    # not a JPEG → refused, and the id is used up
    assert (
        bare_client.post(
            f"/api/intruders?snap={req['id']}", content=b"<svg/>" * 300, headers=AUTH
        ).status_code
        == 400
    )
    bare_client.portal.call(core.request_snap, "stranger")  # type: ignore[union-attr]
    sid = next(iter(core.snaps))
    r = bare_client.post(f"/api/intruders?snap={sid}", content=JPEG, headers=AUTH)
    assert r.status_code == 200
    name = r.json()["file"]
    assert bare_client.get("/api/intruders", headers=AUTH).json() == [name]
    assert bare_client.get(f"/api/intruders/{name}", headers=AUTH).content == JPEG
    assert bare_client.get("/api/intruders/..%2Faudit.sqlite", headers=AUTH).status_code == 404
    assert (core.photos_dir / name).stat().st_mode & 0o777 == 0o600
    # reusing the same id fails
    assert (
        bare_client.post(f"/api/intruders?snap={sid}", content=JPEG, headers=AUTH).status_code
        == 400
    )


def test_photo_feature_off_by_default(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    bare_client.portal.call(core.request_snap, "stranger")  # type: ignore[union-attr]
    assert core.snaps == {}
