import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sasu_core import lifelog
from sasu_core.tools.runtime import Proc
from sasu_core.tools.windows import frames
from tests.conftest import TOKEN


def until(ws: Any, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not out or out[-1]["type"] != kind:
        out.append(json.loads(ws.receive_text()))
    return out


def said(events: list[dict[str, Any]]) -> str:
    return "".join(e["text"] for e in events if e["type"] in ("say_start", "say_chunk"))


class Mac:
    """Fake runner with a clipboard and a volume."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.board = ""
        self.volume = "40"

    async def __call__(self, args: Any, timeout: float = 15, stdin: str | None = None) -> Proc:
        self.calls.append([*args, stdin or ""])
        j = " ".join(args)
        if args == ["pbpaste"]:
            return Proc(0, self.board, "")
        if args == ["pbcopy"]:
            self.board = stdin or ""
        if "output volume of" in j:
            return Proc(0, self.volume, "")
        if "set volume output volume" in j:
            self.volume = args[-1]
        if "bounds of window of desktop" in j:
            return Proc(0, "0, 0, 1440, 900", "")
        if "get {position, size}" in j:
            return Proc(0, "100, 100, 800, 600", "")
        if 'tell application "Notes"' in j:
            return Proc(0, "note-1", "")
        return Proc(0, "", "")


class FakeVoice:
    def __init__(self) -> None:
        self.meeting = False
        self.follow_up = False
        self.follow_timeout = 6.0

    def set_meeting(self, on: bool) -> None:
        self.meeting = on

    def set_speaking(self, on: bool) -> None: ...
    def arm(self, timeout: float = 8.0) -> None: ...
    def stop(self) -> None: ...


# ── parsers ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text", ["start meeting", "Sasu, meeting start", "take meeting notes", "மீட்டிங் ஆரம்பி"]
)
def test_meeting_start(text: str) -> None:
    assert lifelog.MEETING_START.search(text)


@pytest.mark.parametrize(
    ("text", "apps", "layout"),
    [
        ("Safari-um Notes-um side by side", ["Safari", "Notes"], "split"),
        ("Safari and Notes side by side", ["Safari", "Notes"], "split"),
        ("split Chrome and Slack", ["Chrome", "Slack"], "split"),
        ("make Safari full screen", ["Safari"], "full"),
    ],
)
def test_layouts(text: str, apps: list[str], layout: str) -> None:
    assert lifelog.parse_layout(text) == {"apps": apps, "layout": layout}


def test_layout_frames() -> None:
    assert frames("split", 2, 1440, 900) == [(0, 25, 720, 875), (720, 25, 720, 875)]
    assert frames("full", 1, 1440, 900) == [(0, 25, 1440, 875)]


@pytest.mark.parametrize(
    ("clip", "keep"),
    [
        ("https://flights.example/chennai", True),
        ("483920", False),
        ("G-482910", False),
        ("sk-ant-api03-abcdefghijklmnopqrstuvwx", False),
        ("x", False),
    ],
)
def test_clipboard_filter(clip: str, keep: bool) -> None:
    assert lifelog.worth_keeping(clip) is keep


def test_diary_parse() -> None:
    assert (
        lifelog.parse_diary("dear diary: today I finished the Sasu README")
        == "today I finished the Sasu README"
    )
    assert lifelog.parse_diary("diary summary") is None
    assert lifelog.DIARY_ONLY.match("inniku diary")


# ── flows ────────────────────────────────────────────────────────────────────


def test_meeting_notes_saved_to_notes(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.voice = FakeVoice()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "start meeting"}))
        until(ws, "turn_done")
        assert core.voice.meeting is True
        bare_client.portal.call(core.meeting_caption, "Let's ship version four on Friday", "en")  # type: ignore[union-attr]
        caption = until(ws, "caption")[-1]
        assert caption["text"] == "Let's ship version four on Friday"
        bare_client.portal.call(core.meeting_caption, "Ravi will write the release notes", "en")  # type: ignore[union-attr]
        ws.send_text(json.dumps({"type": "text_command", "text": "stop meeting"}))
        events = until(ws, "turn_done")
    assert core.voice.meeting is False
    assert "Saved the transcript in Notes" in said(events)  # no AI key → raw transcript
    note = next(c for c in mac.calls if any('tell application "Notes"' in a for a in c))
    assert "Ravi will write the release notes" in note[-2]
    assert any(e["type"] == "undo_available" for e in events)


def test_sos_sends_after_countdown_and_can_be_cancelled(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.sos_delay = 0.3
    core.sos.update("pineapple rain")
    core.settings.sos_contact = "+44 7700 900123"
    core.settings.city = "London"

    async def run_sos(cancel: bool) -> None:
        core.start_text_turn("pineapple rain")
        await asyncio.sleep(0.05)
        if cancel:
            core.start_text_turn("cancel")
        await core._sos_task

    bare_client.portal.call(run_sos, True)  # type: ignore[union-attr]
    assert not any("send (item 1 of argv)" in " ".join(c) for c in mac.calls)
    bare_client.portal.call(run_sos, False)  # type: ignore[union-attr]
    sent = [c for c in mac.calls if "send (item 1 of argv)" in " ".join(c)]
    assert len(sent) == 1 and sent[0][-2] == "+44 7700 900123" and "London" in sent[0][-3]
    assert "pineapple" not in (core.sos.path.read_text())  # only a salted hash is kept


def test_siren_raises_volume_and_unlock_restores(bare_client: TestClient) -> None:
    from sasu_core.protocol import ControlUnlock

    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.settings.lost_alarm = True
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        for _ in range(3):
            bare_client.portal.call(core.note_stranger)  # type: ignore[union-attr]
        alarm = until(ws, "alarm")[-1]
        assert alarm["kind"] == "siren"
        assert "intruder" in until(ws, "locked")[-1]["reasons"]
    assert mac.volume == "80" and ["pmset", "displaysleepnow", ""] in mac.calls
    bare_client.portal.call(core.control, ControlUnlock(reason="intruder"))  # type: ignore[union-attr]
    assert mac.volume == "40"


def test_siren_is_opt_in(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    for _ in range(3):
        bare_client.portal.call(core.note_stranger)  # type: ignore[union-attr]
    assert core._siren_turn is None and not core.locked


def test_clipboard_memory_recall(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    core.clips.add("https://flights.example/chennai-tomorrow")
    core.clips.add("meeting moved to 3pm")
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "munnaadi copy panna link enna"}))
        events = until(ws, "turn_done")
    assert "flights.example" in said(events)
    assert mac.board == "https://flights.example/chennai-tomorrow"
    assert b"chennai" not in core.clips.path.read_bytes()


def test_window_layout_is_undoable(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    core.runner = mac = Mac()
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "Safari and Notes side by side"}))
        events = until(ws, "turn_done")
        assert any(e["type"] == "undo_available" for e in events)
        ws.send_text(json.dumps({"type": "text_command", "text": "Sasu, undo"}))
        until(ws, "turn_done")
    sets = [c for c in mac.calls if "set position of front window" in " ".join(c)]
    assert sets[0][-6:-1] == ["Safari", "0", "25", "720", "875"]
    assert sets[-1][-6:-1][1:] == ["100", "100", "800", "600"]  # restored


def test_diary_add_and_summary_without_ai(bare_client: TestClient) -> None:
    core = bare_client.app.state.core  # type: ignore[attr-defined]
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "inniku diary"}))
        assert "listening" in said(until(ws, "turn_done"))
        ws.send_text(
            json.dumps(
                {"type": "text_command", "text": "Finished the README and the kids loved the robot"}
            )
        )
        assert "diary" in said(until(ws, "turn_done")).lower()
        ws.send_text(json.dumps({"type": "text_command", "text": "this week's diary summary"}))
        assert "kids loved the robot" in said(until(ws, "turn_done"))
    assert b"README" not in core.diary.path.read_bytes()
