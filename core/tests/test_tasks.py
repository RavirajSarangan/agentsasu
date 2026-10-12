"""Scheduled tasks: parsing, due times, unattended runs that never auto-approve, API."""

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core import tasks
from tests.conftest import TOKEN
from tests.test_bundle_h import Mac, said, until


def at(day_offset: int, hour: int, minute: int = 0) -> float:
    lt = time.localtime(time.time() + day_offset * 86400)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0, 0, 0, -1))


@pytest.mark.parametrize(
    ("text", "req", "when"),
    [
        ("Daily 9 mani-ku mail summary pannu", "mail summary pannu", "Every day at 9:00 AM"),
        ("every Friday 6 pm Downloads clean pannu", "Downloads clean pannu", "Fridays at 6:00 PM"),
        ("weekdays 8:30-ku good morning sollu", "good morning sollu", "Weekdays at 8:30 AM"),
        ("Sasu, every Sunday Desktop clean pannu", "Desktop clean pannu", "Sundays at 9:00 AM"),
        ("good morning sollu every day at 7:30 am", "good morning sollu", "Every day at 7:30 AM"),
        (
            "velli thorum 5 mani Downloads clean pannu",
            "Downloads clean pannu",
            "Fridays at 5:00 PM",
        ),
        ("தினமும் 8 மணிக்கு good morning சொல்லு", "good morning சொல்லு", "Every day at 8:00 AM"),
    ],
)
def test_parse(text: str, req: str, when: str) -> None:
    t = tasks.parse(text)
    assert t is not None and t.request == req and tasks.when(t) == when


@pytest.mark.parametrize("text", ["what is my daily schedule", "volume 30", "every day"])
def test_not_a_task(text: str) -> None:
    assert tasks.parse(text) is None


def test_due_window_and_once_a_day() -> None:
    wday = time.localtime(at(0, 12)).tm_wday
    t = tasks.Task("volume 30", [wday], 9, 0)
    assert not tasks.due(t, at(0, 8, 59))
    assert tasks.due(t, at(0, 9, 0)) and tasks.due(t, at(0, 10, 0))
    assert not tasks.due(t, at(0, 10, 1))  # Mac was asleep: wait for the next day
    t.last_day = time.strftime("%Y-%m-%d", time.localtime(at(0, 12)))
    assert not tasks.due(t, at(0, 9, 30))  # already ran today
    other = tasks.Task("volume 30", [(wday + 1) % 7], 9, 0)
    assert not tasks.due(other, at(0, 9, 30))
    other.enabled = False
    assert not tasks.due(other, at(1, 9, 30))


def test_store_is_encrypted(tmp_path: Path) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    store = tasks.TaskStore(tmp_path / "tasks.bin", AESGCM(AESGCM.generate_key(bit_length=256)))
    t = store.add(tasks.Task("mail summary pannu", [0], 9, 0))
    assert b"summary" not in (tmp_path / "tasks.bin").read_bytes()
    t.last_state = "done"
    store.update(t)
    assert store.get(t.id).last_state == "done"  # type: ignore[union-attr]
    assert store.remove(t.id) and store.all() == []


def test_schedule_by_voice_owner_only(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "Daily 9 mani-ku volume 20 pannu"})
        )
        events = until(ws, "turn_done")
    assert "Every day at 9:00 AM I'll do: “volume 20 pannu”." in said(events)
    assert [t.request for t in core.tasks.all()] == ["volume 20 pannu"]

    async def as_family() -> None:
        core.start_text_turn("every Friday 6 pm Downloads clean pannu", role="family")

    bare_client.portal.call(as_family)  # type: ignore[union-attr]
    assert len(core.tasks.all()) == 1  # family can't schedule


def test_unattended_safe_task_runs(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    wday = time.localtime(at(0, 12)).tm_wday
    t = core.tasks.add(tasks.Task("volume 30", [wday], 9, 0))
    core.clock = lambda: at(0, 9, 1)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.tasks_tick)  # type: ignore[union-attr]
        events = until(ws, "task")
        while events[-1]["state"] == "running":
            events += until(ws, "task")
    assert events[-1]["state"] == "done"
    assert mac.volume == "30"
    saved = core.tasks.get(t.id)
    assert saved.last_state == "done" and saved.last_day == time.strftime(
        "%Y-%m-%d", time.localtime(at(0, 9, 1))
    )
    cmd = next(e for e in reversed(core.audit.recent(30)) if e.kind == "command")
    assert cmd.data["source"] == "schedule"
    bare_client.portal.call(core.tasks_tick)  # type: ignore[union-attr]
    assert [e.data.get("action") for e in core.audit.recent(40) if e.kind == "task"].count(
        "run"
    ) == 1


def test_unattended_never_auto_approves(
    bare_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sasu_core.security.policy.HOME", tmp_path)
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.home = tmp_path
    desk = tmp_path / "Desktop"
    desk.mkdir()
    for name in ("a.pdf", "b.pdf"):
        (desk / name).write_text(name)
        os.utime(desk / name, (time.time() - 3600,) * 2)
    wday = time.localtime(at(0, 12)).tm_wday
    core.tasks.add(tasks.Task("Desktop clean pannu", [wday], 9, 0))
    core.clock = lambda: at(0, 9, 5)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.tasks_tick)  # type: ignore[union-attr]
        events: list[dict[str, Any]] = []
        while not events or events[-1]["type"] != "task" or events[-1]["state"] == "running":
            events.append(json.loads(ws.receive_text()))
        assert events[-1]["state"] == "needs_you"
        assert not any(e["type"] == "confirm_request" for e in events)  # nobody was asked
        assert sorted(p.name for p in desk.iterdir()) == ["a.pdf", "b.pdf"]  # nothing moved
        note = next(c for c in mac.calls if any("display notification" in a for a in c))
        assert "Sasu needs you: Desktop clean pannu" in note[-2]

        ws.send_text(json.dumps({"type": "text_command", "text": "Sasu, run it"}))
        ask = until(ws, "confirm_request")[-1]  # now the owner is here: ask
        ws.send_text(json.dumps({"type": "confirm_response", "id": ask["id"], "approved": True}))
        until(ws, "turn_done")
    assert sorted(p.name for p in desk.iterdir()) == ["PDFs"]
    assert core._needs_you is None


def test_tasks_api(bare_client: TestClient) -> None:
    auth = {"Authorization": f"Bearer {TOKEN}"}
    r = bare_client.post(
        "/api/tasks",
        json={"request": "good morning", "days": [0, 1, 2, 3, 4], "hour": 8, "minute": 30},
        headers=auth,
    )
    tid = r.json()["id"]
    rows = bare_client.get("/api/tasks", headers=auth).json()
    assert [(x["request"], x["when"], x["enabled"]) for x in rows] == [
        ("good morning", "Weekdays at 8:30 AM", True)
    ]
    assert bare_client.post(f"/api/tasks/{tid}/toggle", headers=auth).json() == {"enabled": False}
    assert (
        bare_client.post(
            "/api/tasks", json={"request": "x y z", "days": [9], "hour": 8}, headers=auth
        ).status_code
        == 422
    )
    assert bare_client.post("/api/tasks/nope0000/run", headers=auth).status_code == 404
    assert bare_client.get("/api/tasks").status_code == 401
    assert bare_client.delete(f"/api/tasks/{tid}", headers=auth).json() == {"ok": True}
    assert bare_client.get("/api/tasks", headers=auth).json() == []
