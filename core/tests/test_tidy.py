"""Desktop tidy agent: plan, safety rules, execution through the file tools, undo."""

import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sasu_core import tidy
from tests.conftest import TOKEN
from tests.test_bundle_h import said, until

OLD = time.time() - 3600
WEEKS = time.time() - 30 * 24 * 3600


def put(folder: Path, name: str, data: bytes = b"x", mtime: float = OLD) -> Path:
    p = folder / name
    p.write_bytes(data)
    os.utime(p, (mtime, mtime))
    return p


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("Desktop clean pannu", "Desktop"),
        ("tidy my Downloads", "Downloads"),
        ("Sasu, clean up the desktop", "Desktop"),
        ("Downloads-a suthham pannu", "Downloads"),
        ("organise my downloads", "Downloads"),
        ("டெஸ்க்டாப் சுத்தம் பண்ணு", "Desktop"),
    ],
)
def test_target(text: str, where: str) -> None:
    assert tidy.target(text) == where


@pytest.mark.parametrize("text", ["open my desktop", "clean the kitchen", "what's in downloads"])
def test_not_tidy(text: str) -> None:
    assert tidy.target(text) is None


def test_plan_sorts_bins_and_skips(tmp_path: Path) -> None:
    put(tmp_path, "Screenshot 2026-10-01 at 09.41.png")
    put(tmp_path, "beach.jpg", b"beach")
    put(tmp_path, "beach copy.jpg", b"beach")  # exact duplicate → bin, keep the oldest
    os.utime(tmp_path / "beach copy.jpg", (OLD + 5, OLD + 5))
    put(tmp_path, "lease.pdf", b"lease")
    put(tmp_path, "Zoom.pkg", b"pkg", WEEKS)  # old installer → bin
    put(tmp_path, "Fresh.dmg", b"dmg")  # recent-ish installer → Installers
    put(tmp_path, "notes.weird", b"?")  # unknown kind: left alone
    put(tmp_path, "draft.docx", b"d", time.time())  # changed just now: left alone
    put(tmp_path, ".DS_Store", b"x")  # hidden: left alone
    put(tmp_path, "movie.mp4.crdownload", b"partial")  # still downloading: left alone
    (tmp_path / "Projects").mkdir()  # folders are never touched

    plan = tidy.plan_for(tmp_path)
    names = {k: sorted(p.name for p in v) for k, v in plan.moves.items()}
    assert names == {
        "Images": ["beach.jpg"],
        "Installers": ["Fresh.dmg"],
        "PDFs": ["lease.pdf"],
        "Screenshots": ["Screenshot 2026-10-01 at 09.41.png"],
    }
    assert [p.name for p in plan.dupes] == ["beach copy.jpg"]
    assert [p.name for p in plan.old_installers] == ["Zoom.pkg"]
    assert plan.count == 6
    assert tidy.steps(plan, "en")[-2:] == [
        "Bin 1 exact duplicate",
        "Bin 1 installer older than a week",
    ]
    moves = [c for c in tidy.calls(plan) if c[0] == "files_move"]
    assert all(Path(a["destination"]).parent == tmp_path for _, a in moves)


def test_tidy_turn_moves_then_undo_restores(
    bare_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sasu_core.security.policy.HOME", tmp_path)
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.home = tmp_path
    desk = tmp_path / "Desktop"
    desk.mkdir()
    put(desk, "Screen Shot 1.png", b"1")
    put(desk, "Screen Shot 2.png", b"2")
    put(desk, "report.pdf", b"r")
    put(desk, "report (1).pdf", b"r")
    before = sorted(p.name for p in desk.iterdir())
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "Desktop clean pannu"}))
        plan = until(ws, "plan_preview")[-1]
        assert plan["steps"] == [
            "Move 1 file to PDFs",
            "Move 2 files to Screenshots",
            "Bin 1 exact duplicate",
        ]
        ask = until(ws, "confirm_request")[-1]
        ws.send_text(json.dumps({"type": "confirm_response", "id": ask["id"], "approved": True}))
        events = until(ws, "turn_done")
        assert events[-1]["ok"] is True
        assert "Desktop is tidy: 4 files sorted" in said(events)
        assert sorted(p.name for p in desk.iterdir()) == ["PDFs", "Screenshots"]
        assert sorted(p.name for p in (desk / "Screenshots").iterdir()) == [
            "Screen Shot 1.png",
            "Screen Shot 2.png",
        ]
        undo = next(e for e in events if e["type"] == "undo_available")
        ws.send_text(json.dumps({"type": "undo", "turn_id": undo["turn_id"]}))
        until(ws, "undone")
    assert sorted(p.name for p in desk.iterdir()) == before


def test_tidy_declined_changes_nothing(
    bare_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sasu_core.security.policy.HOME", tmp_path)
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.home = tmp_path
    (tmp_path / "Downloads").mkdir()
    put(tmp_path / "Downloads", "a.pdf")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "tidy my downloads"}))
        ask = until(ws, "confirm_request")[-1]
        ws.send_text(json.dumps({"type": "confirm_response", "id": ask["id"], "approved": False}))
        until(ws, "turn_done")
    assert [p.name for p in (tmp_path / "Downloads").iterdir()] == ["a.pdf"]


def test_already_tidy(bare_client: TestClient, tmp_path: Path) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.home = tmp_path
    (tmp_path / "Desktop").mkdir()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "tidy my desktop"}))
        events = until(ws, "turn_done")
    assert "already tidy" in said(events)
    assert not any(e["type"] == "confirm_request" for e in events)
