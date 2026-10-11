"""Amma mode: elder role, medicine reminders, calling family, the help alert."""

import asyncio
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core import care
from sasu_core.security.roles import allowed
from sasu_core.tools.runtime import Proc
from tests.conftest import TOKEN
from tests.test_bundle_h import FakeVoice, Mac, said, until


def at(hour: int, minute: int = 0) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0, 0, 0, -1))


# ── parsers ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "who", "what", "hour", "minute"),
    [
        ("Amma-ku 8 mani BP maathirai reminder vai", "amma", "BP maathirai", 8, 0),
        ("remind appa to take his sugar tablet at 9 pm", "appa", "sugar tablet", 21, 0),
        ("Hey Sasu, remind amma to take BP tablet at 8:30 am", "amma", "BP tablet", 8, 30),
        ("அம்மாவுக்கு 8 மணிக்கு BP மாத்திரை நினைவூட்டு", "amma", "BP மாத்திரை", 8, 0),
        ("appa ku raathiri 9 mani sugar maathirai reminder vai", "appa", "sugar maathirai", 21, 0),
        ("paati-ku 3 mani juice reminder vai", "paati", "juice", 15, 0),
    ],
)
def test_parse_reminder(text: str, who: str, what: str, hour: int, minute: int) -> None:
    d = care.parse_reminder(text)
    assert d is not None
    assert (d.who, d.what, d.hour, d.minute) == (who, what, hour, minute)


@pytest.mark.parametrize("text", ["remind me later", "amma is at home", "set a timer for 8"])
def test_not_a_reminder(text: str) -> None:
    assert care.parse_reminder(text) is None


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("call Raviraj", "Raviraj"),
        ("magan-ku call pannu", "magan"),
        ("Magal ku phone pannu", "Magal"),
        ("மகனுக்கு போன் பண்ணு", "மகனு"),
    ],
)
def test_call_target(text: str, target: str) -> None:
    assert care.call_target(text) == target


@pytest.mark.parametrize("text", ["help", "help me please", "udhavi", "உதவி பண்ணுங்க"])
def test_help_words(text: str) -> None:
    assert care.HELP.search(text)


def test_elder_role_is_like_family() -> None:
    assert allowed("elder", "shell_run", {}, "safe") == "deny"
    assert allowed("elder", "files_trash", {}, "dangerous") == "deny"
    assert allowed("elder", "call_contact", {"number": "+1 555 0100"}, "confirm") == "confirm"


def test_tracker_ask_repeat_missed() -> None:
    d = care.Dose("d1", "amma", "BP tablet", 8, 0)
    t = care.Tracker()
    assert t.actions([d], at(7, 59)) == []
    assert t.actions([d], at(8, 0)) == [("ask", d)]
    assert t.actions([d], at(8, 5)) == []
    assert t.actions([d], at(8, 15)) == [("repeat", d)]
    assert t.actions([d], at(8, 30)) == [("missed", d)]
    assert t.actions([d], at(9, 0)) == []
    late = care.Tracker()
    assert late.actions([d], at(11, 0)) == []  # never nags hours later


def test_care_store_is_encrypted(tmp_path: Any) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    store = care.CareStore(tmp_path / "care.bin", AESGCM(AESGCM.generate_key(bit_length=256)))
    store.add(care.Dose("d1", "amma", "BP maathirai", 8, 0))
    assert b"maathirai" not in (tmp_path / "care.bin").read_bytes()
    assert [d.what for d in store.all()] == ["BP maathirai"]
    assert store.remove("d1") and store.all() == []


# ── flows ────────────────────────────────────────────────────────────────────


def test_spoken_reminder_is_saved(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(
            json.dumps({"type": "text_command", "text": "Amma-ku 8 mani BP maathirai reminder vai"})
        )
        events = until(ws, "turn_done")
    assert "8:00 AM" in said(events)
    assert [(d.who, d.hour) for d in core.care_store.all()] == [("amma", 8)]


def test_due_dose_asks_in_big_tamil_then_aamaa_marks_taken(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    core.voice = FakeVoice()
    core.care_store.add(care.Dose("d1", "amma", "BP மாத்திரை", 8, 0))
    core.clock = lambda: at(8, 1)
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.care_tick)  # type: ignore[union-attr]
        events = until(ws, "say_end")
        due = next(e for e in events if e["type"] == "care")
        assert (due["kind"], due["who"], due["time"]) == ("due", "amma", "08:00")
        start = next(e for e in events if e["type"] == "say_start")
        assert start["big"] is True and start["lang"] == "ta"
        assert "அம்மா, BP மாத்திரை நேரம்" in said(events)
        assert core.voice.follow_up is True
        ws.send_text(json.dumps({"type": "text_command", "text": "aamaa"}))
        events = until(ws, "turn_done")
    assert any(e["type"] == "care" and e["kind"] == "taken" for e in events)
    assert core.care.pending() == []


def test_unconfirmed_dose_repeats_then_texts_family(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.settings.sos_contact = "+44 7700 900123"
    core.care_store.add(care.Dose("d1", "appa", "sugar tablet", 21, 0))
    for minute in (0, 15, 30):
        core.clock = lambda m=minute: at(21, m)
        bare_client.portal.call(core.care_tick)  # type: ignore[union-attr]
    sent = [c for c in mac.calls if "send (item 1 of argv)" in " ".join(c)]
    assert len(sent) == 1 and sent[0][-2] == "+44 7700 900123"
    assert "appa hasn't confirmed taking sugar tablet" in sent[0][-3]
    kinds = [e.data.get("action") for e in reversed(core.audit.recent(20)) if e.kind == "care"]
    assert kinds[-3:] == ["ask", "repeat", "missed"]


class Contacts(Mac):
    async def __call__(self, args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        if 'tell application "Contacts"' in " ".join(args):
            self.calls.append([*args, stdin or ""])
            return Proc(0, "Raviraj Sarangan: +44 7700 900456", "")
        return await super().__call__(args, timeout, stdin)


def test_call_son_by_relation_asks_then_calls(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Contacts()
    core.relations = {"son": "Raviraj"}
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "மகனுக்கு போன் பண்ணு"}))
        ask = until(ws, "confirm_request")[-1]
        ws.send_text(json.dumps({"type": "text_command", "text": "aamaa"}))  # a spoken yes
        events = until(ws, "turn_done")
    lookup = next(c for c in mac.calls if 'tell application "Contacts"' in " ".join(c))
    assert lookup[-2] == "Raviraj"  # the name travels in argv, never inside the script
    assert ["open", "facetime-audio://+447700900456", ""] in mac.calls
    assert ask["risk"] == "confirm" and events[-1]["ok"] is True


def test_call_refused_by_voice(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Contacts()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "call Raviraj"}))
        until(ws, "confirm_request")
        ws.send_text(json.dumps({"type": "text_command", "text": "venaam"}))
        until(ws, "turn_done")
    assert not any(c[0] == "open" for c in mac.calls)


@pytest.mark.parametrize("number", ["555; rm -rf /", "facetime://x", "12"])
def test_call_contact_rejects_bad_numbers(number: str) -> None:
    from sasu_core.tools.contacts import NUMBER

    assert not NUMBER.match(number)


def test_elder_help_counts_down_and_can_be_cancelled(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.help_delay = 0.3
    core.settings.sos_contact = "+44 7700 900123"
    core._last_speaker = ("Amma", "elder")

    async def run_help(cancel: bool) -> None:
        core.start_text_turn("udhavi", role="elder", lang="ta")
        await asyncio.sleep(0.05)
        if cancel:
            core.start_text_turn("cancel", role="elder")
        await core._sos_task

    bare_client.portal.call(run_help, True)  # type: ignore[union-attr]
    assert not any("send (item 1 of argv)" in " ".join(c) for c in mac.calls)
    bare_client.portal.call(run_help, False)  # type: ignore[union-attr]
    sent = [c for c in mac.calls if "send (item 1 of argv)" in " ".join(c)]
    assert len(sent) == 1 and "Amma asked Sasu for help" in sent[0][-3]


def test_help_is_elder_only(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    core.settings.sos_contact = "+44 7700 900123"

    async def run() -> None:
        core.start_text_turn("help me write an email", role="owner")
        await asyncio.sleep(0.05)

    bare_client.portal.call(run)  # type: ignore[union-attr]
    assert core._sos_task is None


def test_care_api(bare_client: TestClient) -> None:
    auth = {"Authorization": f"Bearer {TOKEN}"}
    r = bare_client.post(
        "/api/care", json={"who": "amma", "what": "BP tablet", "hour": 8}, headers=auth
    )
    did = r.json()["id"]
    rows = bare_client.get("/api/care", headers=auth).json()
    assert [(c["who"], c["hour"], c["status"]) for c in rows] == [("amma", 8, "upcoming")]
    assert (
        bare_client.post(
            "/api/care", json={"who": "amma", "what": "x", "hour": 25}, headers=auth
        ).status_code
        == 422
    )
    assert bare_client.get("/api/care").status_code == 401
    assert bare_client.delete(f"/api/care/{did}", headers=auth).json() == {"ok": True}
    assert bare_client.get("/api/care", headers=auth).json() == []
