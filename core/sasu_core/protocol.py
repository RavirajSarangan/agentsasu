"""WebSocket protocol between sasu-core and the desktop UI.

This module is the single source of truth. `python -m sasu_core.protocol` prints the
JSON schema that packages/protocol/schema.json is generated from.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

Lang = Literal["en", "ta"]
Risk = Literal["safe", "confirm", "dangerous"]


# ── core → UI ────────────────────────────────────────────────────────────────


class Ready(BaseModel):
    type: Literal["ready"] = "ready"
    version: str
    demo: bool


class Wake(BaseModel):
    type: Literal["wake"] = "wake"
    source: Literal["wakeword", "hotkey", "click", "demo"]


class Listening(BaseModel):
    type: Literal["listening"] = "listening"


class PartialTranscript(BaseModel):
    type: Literal["partial_transcript"] = "partial_transcript"
    text: str


class Transcript(BaseModel):
    type: Literal["transcript"] = "transcript"
    text: str
    lang: Lang


class Thinking(BaseModel):
    type: Literal["thinking"] = "thinking"


class ToolStart(BaseModel):
    type: Literal["tool_start"] = "tool_start"
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = "safe"


class ToolEnd(BaseModel):
    type: Literal["tool_end"] = "tool_end"
    id: str
    ok: bool
    summary: str = ""


class ConfirmRequest(BaseModel):
    type: Literal["confirm_request"] = "confirm_request"
    id: str
    prompt: str
    lang: Lang
    risk: Risk


class SayStart(BaseModel):
    type: Literal["say_start"] = "say_start"
    text: str
    lang: Lang
    big: bool = False  # Amma mode: large, easy-to-read captions


class SayChunk(BaseModel):
    type: Literal["say_chunk"] = "say_chunk"
    text: str


class SayEnd(BaseModel):
    type: Literal["say_end"] = "say_end"


class TurnDone(BaseModel):
    type: Literal["turn_done"] = "turn_done"
    ok: bool


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class Sleep(BaseModel):
    type: Literal["sleep"] = "sleep"


LockReason = Literal["screen", "disabled", "user", "panic", "canary", "away", "intruder"]


class SpeakerRejected(BaseModel):
    """Someone who is not the enrolled owner spoke. Nothing was run."""

    type: Literal["speaker_rejected"] = "speaker_rejected"
    score: float


class Locked(BaseModel):
    type: Literal["locked"] = "locked"
    reasons: list[LockReason]


class Unlocked(BaseModel):
    type: Literal["unlocked"] = "unlocked"


class AuthRequired(BaseModel):
    """A dangerous action needs Touch ID / password, handled by the desktop shell."""

    type: Literal["auth_required"] = "auth_required"
    id: str
    reason: str
    risk: Risk


class PlanPreview(BaseModel):
    """What Sasu is about to do, shown before a multi-step or risky turn."""

    type: Literal["plan_preview"] = "plan_preview"
    id: str
    steps: list[str]


class FocusApp(BaseModel):
    """Sasu is working in this app (the robot flies next to it)."""

    type: Literal["focus_app"] = "focus_app"
    app: str


class UndoAvailable(BaseModel):
    type: Literal["undo_available"] = "undo_available"
    turn_id: str
    actions: list[str]


class Undone(BaseModel):
    type: Literal["undone"] = "undone"
    turn_id: str
    ok: bool
    summary: str


class Privacy(BaseModel):
    """What left this Mac during the turn."""

    type: Literal["privacy"] = "privacy"
    provider: str
    chars: int
    images: int = 0
    audio: int = 0


class Level(BaseModel):
    """Mic input level 0–1, for meters."""

    type: Literal["level"] = "level"
    rms: float


class EnrollProgress(BaseModel):
    type: Literal["enroll_progress"] = "enroll_progress"
    n: int
    total: int
    phrase: str
    done: bool = False


class FocusState(BaseModel):
    """Focus mode countdown (seconds left; 0 = ended)."""

    type: Literal["focus"] = "focus"
    remaining: int
    total: int


class TranslateMode(BaseModel):
    type: Literal["translate_mode"] = "translate_mode"
    on: bool


class SnapRequest(BaseModel):
    """Take one camera photo now and upload it to /api/intruders?snap=<id> (opt-in feature)."""

    type: Literal["snap_request"] = "snap_request"
    id: str
    reason: str


class Caption(BaseModel):
    """Live meeting caption (on-device speech-to-text)."""

    type: Literal["caption"] = "caption"
    text: str
    lang: Lang


class MeetingState(BaseModel):
    type: Literal["meeting"] = "meeting"
    on: bool
    seconds: int = 0
    lines: int = 0


class WatchState(BaseModel):
    """Watch & tell: something Sasu is keeping an eye on."""

    type: Literal["watch"] = "watch"
    id: str
    kind: Literal["download", "battery", "page", "file", "command"]
    label: str
    state: Literal["started", "fired", "stopped"]


class Care(BaseModel):
    """Amma mode: a medicine reminder was asked, confirmed or missed."""

    type: Literal["care"] = "care"
    kind: Literal["due", "taken", "missed", "help"]
    who: str
    what: str = ""
    time: str = ""


class Idle(BaseModel):
    """Listening ended with nothing to do; the robot relaxes."""

    type: Literal["idle"] = "idle"


class Alarm(BaseModel):
    """Something tried to misuse Sasu (trap file touched, data leak blocked)."""

    type: Literal["alarm"] = "alarm"
    kind: Literal["canary", "leak", "panic", "siren", "sos"]
    detail: str


class Intruder(BaseModel):
    """Someone other than the owner tried a command."""

    type: Literal["intruder"] = "intruder"
    text: str
    score: float
    count: int


class Fun(BaseModel):
    """Playful robot moments (dancing while music plays…)."""

    type: Literal["fun"] = "fun"
    kind: Literal["dance", "joke", "night", "briefing", "festival"]
    on: bool = True
    detail: str = ""  # e.g. the song that's playing


class VoiceStatus(BaseModel):
    """On-device voice: models missing / downloading / ready / listening / error."""

    type: Literal["voice_status"] = "voice_status"
    state: Literal["missing", "downloading", "loading", "listening", "error"]
    progress: float = 0.0
    detail: str = ""
    size_mb: int = 0
    enrolled: bool = False
    profiles: list[str] = Field(default_factory=list)  # "Amma (family)"


class BrainStatus(BaseModel):
    type: Literal["brain_status"] = "brain_status"
    provider: str
    model: str
    ready: bool
    keys: list[str]
    voice: bool


CoreEvent = Annotated[
    Ready
    | Wake
    | Listening
    | PartialTranscript
    | Transcript
    | Thinking
    | ToolStart
    | ToolEnd
    | ConfirmRequest
    | SayStart
    | SayChunk
    | SayEnd
    | TurnDone
    | ErrorEvent
    | Sleep
    | SpeakerRejected
    | Locked
    | Unlocked
    | AuthRequired
    | PlanPreview
    | FocusApp
    | UndoAvailable
    | Undone
    | Privacy
    | Level
    | EnrollProgress
    | BrainStatus
    | VoiceStatus
    | Alarm
    | Intruder
    | Fun
    | Idle
    | FocusState
    | TranslateMode
    | SnapRequest
    | Caption
    | MeetingState
    | Care
    | WatchState,
    Field(discriminator="type"),
]


# ── UI → core ────────────────────────────────────────────────────────────────


class PttStart(BaseModel):
    type: Literal["ptt_start"] = "ptt_start"


class PttStop(BaseModel):
    type: Literal["ptt_stop"] = "ptt_stop"


class TextCommand(BaseModel):
    type: Literal["text_command"] = "text_command"
    text: str


class ConfirmResponse(BaseModel):
    type: Literal["confirm_response"] = "confirm_response"
    id: str
    approved: bool


class Cancel(BaseModel):
    type: Literal["cancel"] = "cancel"


class SetSettings(BaseModel):
    type: Literal["set_settings"] = "set_settings"
    settings: dict[str, Any]


class Lock(BaseModel):
    """Any window may lock Sasu. Only the desktop shell (stdin) can unlock it."""

    type: Literal["lock"] = "lock"


class Undo(BaseModel):
    type: Literal["undo"] = "undo"
    turn_id: str | None = None


class EnrollStart(BaseModel):
    type: Literal["enroll_start"] = "enroll_start"
    name: str = Field(default="Owner", max_length=40)
    role: Literal["owner", "family", "elder", "kid"] = "owner"


class ProfileRemove(BaseModel):
    type: Literal["profile_remove"] = "profile_remove"
    name: str


class EnrollCancel(BaseModel):
    type: Literal["enroll_cancel"] = "enroll_cancel"


class SayPreview(BaseModel):
    """Speak a short sample in the current voice (settings preview)."""

    type: Literal["say_preview"] = "say_preview"


class VoiceSetup(BaseModel):
    """Download the on-device voice models (one time) and start listening."""

    type: Literal["voice_setup"] = "voice_setup"


class SkillRun(BaseModel):
    type: Literal["skill_run"] = "skill_run"
    name: str


UiCommand = Annotated[
    PttStart
    | PttStop
    | TextCommand
    | ConfirmResponse
    | Cancel
    | SetSettings
    | Lock
    | Undo
    | EnrollStart
    | EnrollCancel
    | SkillRun
    | VoiceSetup
    | SayPreview
    | ProfileRemove,
    Field(discriminator="type"),
]


# ── shell → core (stdin control channel; only the Tauri process holds it) ─────


class ControlLock(BaseModel):
    type: Literal["lock"] = "lock"
    reason: LockReason


class ControlUnlock(BaseModel):
    type: Literal["unlock"] = "unlock"
    reason: LockReason


class ControlAuthResult(BaseModel):
    type: Literal["auth_result"] = "auth_result"
    id: str
    ok: bool


class ControlCancel(BaseModel):
    type: Literal["cancel"] = "cancel"


class ControlSecret(BaseModel):
    """An AI provider key from the Keychain. Empty key = remove."""

    type: Literal["secret"] = "secret"
    provider: str
    key: str


Control = Annotated[
    ControlLock | ControlUnlock | ControlAuthResult | ControlCancel | ControlSecret,
    Field(discriminator="type"),
]


class StdinConfig(BaseModel):
    """First stdin line from the shell: secrets never travel through argv or env."""

    token: str = Field(min_length=32)
    data_dir: str
    vault_key: str = Field(min_length=64, max_length=64)
    dev: bool = False


core_event_adapter: TypeAdapter[CoreEvent] = TypeAdapter(CoreEvent)
ui_command_adapter: TypeAdapter[UiCommand] = TypeAdapter(UiCommand)
control_adapter: TypeAdapter[Control] = TypeAdapter(Control)


def json_schema() -> dict[str, Any]:
    return {
        "coreEvent": core_event_adapter.json_schema(),
        "uiCommand": ui_command_adapter.json_schema(),
    }


if __name__ == "__main__":
    print(json.dumps(json_schema(), indent=2, sort_keys=True))
