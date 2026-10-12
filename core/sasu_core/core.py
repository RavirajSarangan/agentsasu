"""The running agent: turns, approvals, locks, brain, undo, skills."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import assist, briefing, care, extras, fastpath, focus, lifelog, tasks, tidy, watch
from . import memory as mem
from .brain.agent import Agent, Executor, Turn
from .brain.providers import SPECS, ChatClient, LLMError, pick_model
from .demo import detect_lang, scripted_turn
from .fun import JOKE, REPORT, PanicWord, joke, security_report
from .hub import Hub
from .protocol import (
    Alarm,
    AuthRequired,
    BrainStatus,
    Cancel,
    Caption,
    Care,
    ConfirmRequest,
    ConfirmResponse,
    Control,
    ControlAuthResult,
    ControlCancel,
    ControlLock,
    ControlSecret,
    ControlUnlock,
    EnrollCancel,
    EnrollProgress,
    EnrollStart,
    ErrorEvent,
    FocusState,
    Fun,
    Idle,
    Intruder,
    Lang,
    Level,
    Listening,
    Lock,
    Locked,
    LockReason,
    MeetingState,
    Privacy,
    ProfileRemove,
    PttStart,
    Risk,
    SayChunk,
    SayEnd,
    SayPreview,
    SayStart,
    SetSettings,
    SkillRun,
    SnapRequest,
    SpeakerRejected,
    TaskState,
    TextCommand,
    Thinking,
    Transcript,
    TranslateMode,
    TurnDone,
    UiCommand,
    Undo,
    UndoAvailable,
    Undone,
    Unlocked,
    VoiceSetup,
    VoiceStatus,
    Wake,
    WatchState,
)
from .security.audit import AuditLog
from .security.canary import Canaries
from .security.voiceprint import Profile, Voiceprint, VoiceprintVault, identify
from .skills import SAVE, UNDO, Skills
from .tools import ToolContext
from .tts.macos import Speaker
from .undo import Journal, undo_turn
from .voice import models as voice_models
from .voice.pipeline import Callbacks, Heard, VoicePipeline

ENROLL_PHRASES = [
    "Hey Sasu, open Safari",
    "சாசு, Downloads-ல இருக்கிற PDF காட்டு",
    "Hey Sasu, what's on my calendar today?",
    "சாசு, ஒரு நல்ல பாட்டு போடு",
    "Hey Sasu, set the volume to thirty",
]

CONFIRM_TIMEOUT_S = 30.0
AUTH_TIMEOUT_S = 60.0


@dataclass
class Pending:
    kind: Literal["confirm", "auth"]
    future: asyncio.Future[bool] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


@dataclass
class BrainSettings:
    provider: str = "gemini"
    model: str | None = None
    tts: bool = True
    guest_mode: Literal["guest", "reject"] = "guest"
    fun_replies: bool = False
    away_minutes: int = 0
    voice_style: Literal["girl", "boy"] = "girl"
    robot_name: str = "Sasu"
    city: str = ""
    intruder_photo: bool = False
    nudges: bool = False
    festivals: bool = True
    sos_contact: str = ""
    lost_alarm: bool = False
    clipboard_memory: bool = False
    distractions: list[str] = field(default_factory=lambda: list(focus.DEFAULT_DISTRACTIONS))


class Core:
    def __init__(
        self,
        hub: Hub,
        audit: AuditLog,
        vault: VoiceprintVault,
        data_dir: Path,
        *,
        demo: bool,
        delay: float,
        speaker: Speaker | None = None,
    ) -> None:
        self.hub, self.audit, self.vault = hub, audit, vault
        self.demo, self.delay = demo, delay
        self.journal = Journal(data_dir / "undo.sqlite")
        self.skills = Skills(data_dir / "skills.json")
        self.holding = data_dir / "bin"
        self.speaker = speaker or Speaker()
        self.settings = BrainSettings()
        self.keys: dict[str, str] = {}  # in memory only; the shell owns storage
        self.models: dict[str, str] = {}
        self.locks: set[LockReason] = set()
        self.pending: dict[str, Pending] = {}
        self.history: deque[dict[str, Any]] = deque(maxlen=8)
        self.last_calls: list[dict[str, Any]] = []
        self.transport: Any = None  # tests inject a fake model server
        from .tools.runtime import run as _run

        self.runner: Any = _run  # tests inject a fake so nothing really runs
        self._turn: asyncio.Task[None] | None = None
        self.models_dir = data_dir / "models"
        self.voice: VoicePipeline | None = None
        self.voice_state = VoiceStatus(
            state="missing", size_mb=voice_models.TOTAL_BYTES // 1_000_000
        )
        self._enroll: list[list[float]] | None = None
        self._setup: asyncio.Task[None] | None = None
        self.canaries = Canaries(data_dir / "canaries.json")
        self.panic = PanicWord(data_dir / "panic.json")
        self.intruders_unseen: list[str] = []
        self.owner_verified_at = 0.0
        self._enroll_who: tuple[str, str] = ("Owner", "owner")
        self._role = "owner"
        self._focus: asyncio.Task[None] | None = None
        self._focus_turn: str | None = None
        self.translating = False
        self.memory = mem.Memory(data_dir / "memory.bin", vault.aead)
        self.photos_dir = data_dir / "intruders"
        self.snaps: dict[str, float] = {}
        self._greeted_festival = ""
        self.sos = PanicWord(data_dir / "sos.json")
        self._sos_task: asyncio.Task[None] | None = None
        self._sos_cancel: asyncio.Event | None = None
        self.sos_delay = 5.0  # seconds to say "cancel"
        self.help_delay = 10.0  # Amma mode "help": a little longer to cancel
        self.care_store = care.CareStore(data_dir / "care.bin", vault.aead)
        self.care = care.Tracker()
        self.relations: dict[str, str] = {}
        self.home = Path.home()  # where Desktop / Downloads live (tests point it elsewhere)
        self.watches: dict[str, tuple[watch.Watch, asyncio.Task[None]]] = {}
        self._bg: asyncio.Task[None] | None = None
        self.tasks = tasks.TaskStore(data_dir / "tasks.bin", vault.aead)
        self._unattended: str | None = None  # id of the scheduled task running now
        self._blocked: str | None = None  # the question an unattended run couldn't ask
        self._needs_you: str | None = None  # task waiting for "Sasu, run it"
        self._last_said = ""
        self.watch_every = {
            "download": 2.0,
            "file": 5.0,
            "battery": 60.0,
            "page": 600.0,
        }  # "son" → "Raviraj" (Settings → Family → Care)
        self.clock = __import__("time").time
        self._siren_turn: str | None = None
        self._strangers: deque[float] = deque(maxlen=10)
        self.meeting: list[str] | None = None
        self._meeting_started = 0.0
        self._meeting_lang: Lang = "en"
        self.diary = mem.Memory(data_dir / "diary.bin", vault.aead, b"sasu-diary-v1", limit=2000)
        self.clips = mem.Memory(data_dir / "clips.bin", vault.aead, b"sasu-clipboard-v1", limit=50)
        self._diary_next = False  # pending snap id → expiry (monotonic)
        self._last_speaker: tuple[str, str] = ("Owner", "owner")
        self.last_lang: Lang = "en"
        self._watchers: list[asyncio.Task[None]] = []

    # ── state ──────────────────────────────────────────────────────────────
    @property
    def locked(self) -> bool:
        return bool(self.locks)

    @property
    def brain_ready(self) -> bool:
        spec = SPECS.get(self.settings.provider)
        return bool(spec and (not spec.needs_key or self.keys.get(spec.id)))

    def brain_status(self) -> BrainStatus:
        spec = SPECS.get(self.settings.provider, SPECS["gemini"])
        model = self.models.get(spec.id) or self.settings.model or spec.default_model
        return BrainStatus(
            provider=spec.id,
            model=model,
            ready=self.brain_ready,
            keys=sorted(self.keys),
            voice=self.speaker.enabled and self.settings.tts,
        )

    # ── turns ──────────────────────────────────────────────────────────────
    def _start(self, coro: Any) -> None:
        self.cancel()
        self._turn = asyncio.create_task(coro)

    def cancel(self) -> bool:
        self._deny_all()
        self.speaker.stop()
        if self._turn and not self._turn.done():
            self._turn.cancel()
            return True
        return False

    async def _stop(self, code: str, message: str) -> None:
        if self.cancel():
            await self.hub.emit(ErrorEvent(code=code, message=message))
            await self.hub.emit(TurnDone(ok=False))

    def start_text_turn(
        self, text: str, *, guest: bool = False, lang: Lang | None = None, role: str = "owner"
    ) -> None:
        text = text.strip()
        if not guest and self._voice_answer(text):
            return  # "yes" / "no" to a pending question, by voice (keeps the asker's role)
        self._role = "guest" if guest else role
        if self.panic.heard_in(text):
            self._start(self.panic_lock())
            return
        if self._sos_cancel is not None and lifelog.CANCEL.search(text):
            self._sos_cancel.set()
            return
        if self.care.pending() and (care.CONFIRM_YES.match(text) or care.CONFIRM_NO.match(text)):
            self._start(
                self.dose_answer(bool(care.CONFIRM_YES.match(text)), lang or detect_lang(text))
            )
            return
        if role == "elder" and care.HELP.search(text):
            self._sos_task = asyncio.create_task(
                self.sos_turn(lang or detect_lang(text), help=True)
            )
            return
        if not guest and role in ("owner", "family", "elder"):
            if (dose := care.parse_reminder(text)) is not None:
                self._start(self.add_reminder(dose, lang or detect_lang(text)))
                return
            if (target := care.call_target(text)) is not None:
                self._start(self.call_turn(target, lang or detect_lang(text)))
                return
        if not guest and role in ("owner", "family") and self.sos.heard_in(text):
            self._sos_task = asyncio.create_task(self.sos_turn(lang or detect_lang(text)))
            return
        if self.meeting is not None:
            if lifelog.MEETING_STOP.search(text):
                self._start(self.end_meeting())
            return
        if not guest and role == "owner" and self._diary_next:
            self._diary_next = False
            self._start(self.diary_add(text, lang or detect_lang(text)))
            return
        if not guest and self.intruders_unseen:
            notice = self.intruders_unseen
            self.intruders_unseen = []
            self._start(self._notice_then(notice, text, lang))
            return
        if self.translating and not guest:
            if assist.TRANSLATE_OFF.search(text):
                self._start(self.set_translate(False))
            else:
                self._start(self.translate_turn(text, lang or detect_lang(text)))
            return
        if not guest and role == "owner":
            if lifelog.MEETING_START.search(text):
                self._start(self.start_meeting(lang or detect_lang(text)))
                return
            if lifelog.DIARY_SUMMARY.search(text):
                self._start(self.diary_summary(lang or detect_lang(text)))
                return
            if (entry := lifelog.parse_diary(text)) is not None:
                self._start(self.diary_add(entry, lang or detect_lang(text)))
                return
            if lifelog.DIARY_ONLY.match(text.strip()):
                self._diary_next = True
                self._start(
                    self._say_turn(
                        "Go ahead, I'm listening."
                        if (lang or detect_lang(text)) != "ta"
                        else "சொல்லுங்க, கேக்கறேன்.",
                        lang or detect_lang(text),
                    )
                )
                return
            if lifelog.CLIP_RECALL.search(text):
                self._start(self.clip_recall(text, lang or detect_lang(text)))
                return
            if (layout := lifelog.parse_layout(text)) is not None:
                self._start(
                    self.fast_turn(
                        text,
                        fastpath.Fast(
                            [("windows_arrange", layout)], "Done.", "முடிஞ்சது.", "windows"
                        ),
                        lang or detect_lang(text),
                    )
                )
                return
            if (fact := mem.parse_save(text)) is not None:
                self._start(self.remember(fact, lang or detect_lang(text)))
                return
            if (what := mem.parse_forget(text)) is not None:
                self._start(self.forget(what))
                return
            if mem.RECALL.search(text):
                self._start(self.recall(text, lang or detect_lang(text)))
                return
        if not guest and role in ("owner", "family"):
            if (typed := extras.parse_type(text)) is not None:
                self._start(self.voice_type(typed, lang or detect_lang(text)))
                return
            if extras.is_read(text):
                self._start(self.read_aloud())
                return
            if role == "owner" and (task := tasks.parse(text)) is not None:
                self._start(self.add_task(task, text, lang or detect_lang(text)))
                return
            if self._needs_you and tasks.RUN_IT.match(text):
                self._bg = asyncio.create_task(self.run_task_now(self._needs_you))
                return
            if watch.STOP.search(text):
                self._start(self.stop_watches(lang or detect_lang(text)))
                return
            if watch.LIST.search(text):
                self._start(self.list_watches(lang or detect_lang(text)))
                return
            if (wreq := watch.parse(text)) is not None:
                self._start(self.start_watch(wreq, text, lang or detect_lang(text)))
                return
            if (where := tidy.target(text)) is not None and len(text.split()) <= 8:
                self._start(self.tidy_turn(where, text, lang or detect_lang(text)))
                return
            if assist.TRANSLATE_ON.search(text) and len(text.split()) <= 5:
                self._start(self.set_translate(True))
                return
            if assist.CLIPBOARD.search(text):
                self._start(self.translate_clipboard(assist.clipboard_target(text)))
                return
            if assist.SCREEN.search(text) and len(text.split()) <= 10:
                self._start(self.explain_screen(text, lang or detect_lang(text)))
                return
        if guest or role == "kid":  # guests and kids get a small tool set, nothing else
            fast = fastpath.parse(text)
            if fast is not None:
                self._start(self.fast_turn(text, fast, lang or detect_lang(text), guest=True))
            elif self.brain_ready:
                self._start(self.agent_turn(text, guest=True, lang=lang))
            else:
                self._start(self._no_brain(text))
        elif UNDO.match(text):
            self._start(self.undo(None))
        elif m := SAVE.match(text):
            self._start(self.save_skill(m.group("name")))
        elif name := self.skills.match(text):
            self._start(self.run_skill(name))
        elif REPORT.search(text) and len(text.split()) <= 6:
            self._start(self.report())
        elif JOKE.search(text) and len(text.split()) <= 6:
            self._start(self.tell_joke(lang or detect_lang(text)))
        elif briefing.TRIGGER.search(text) and len(text.split()) <= 6:
            self._start(self.morning_briefing(lang or detect_lang(text)))
        elif focus.is_stop(text):
            self._start(self.stop_focus())
        elif (mins := focus.parse_start(text)) is not None:
            self._start(self.start_focus(mins, lang or detect_lang(text)))
        elif (fast := fastpath.parse(text)) is not None:
            self._start(self.fast_turn(text, fast, lang or detect_lang(text)))
        elif self.brain_ready:
            self._start(self.agent_turn(text, lang=lang))
        elif self.demo:
            self._start(
                scripted_turn(self.hub.emit, text, delay=self.delay, approve=self._approve_demo)
            )
        else:
            self._start(self._no_brain(text))

    async def _notice_then(self, attempts: list[str], text: str, lang: Lang | None) -> None:
        n = len(attempts)
        await self.speak(
            f"Heads up: someone else tried to use me {n} time{'s' if n != 1 else ''} while you were away. It's in the intruder log.",
            "en",
        )
        self.start_text_turn(text, lang=lang)

    async def panic_lock(self) -> None:
        self.audit.append("alarm", alarm="panic", detail="panic word heard")
        await self.hub.emit(Alarm(kind="panic", detail="Panic word heard. Locked."))
        await self.lock("panic")

    async def report(self) -> None:
        await self.hub.emit(Thinking())
        await self.speak(security_report(self.audit), "en")
        await self.hub.emit(TurnDone(ok=True))

    async def morning_briefing(self, lang: Lang) -> None:
        await self.hub.emit(Thinking())
        info = await briefing.gather(self.runner, self.settings.city, self.transport)
        name = self._last_speaker[0] if self._last_speaker[0] != "Owner" else ""
        self.audit.append("briefing", weather=bool(info.get("weather")), events=len(info["events"]))
        await self.hub.emit(Fun(kind="briefing"))
        await self.speak(briefing.compose(info, lang, name), lang)
        await self.hub.emit(TurnDone(ok=True))

    async def start_focus(self, minutes: int, lang: Lang) -> None:
        from .tools.runtime import applescript

        if self._focus and not self._focus.done():
            await self.stop_focus(silent=True)
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role=self._role)
        turn.plan_approved = True  # the user asked for focus explicitly
        ex = self._executor()
        running = await self.runner(
            applescript(
                'tell application "System Events" to get name of every process whose background only is false'
            ),
            5,
            None,
        )
        open_now = {n.strip() for n in running.out.split(",")}
        closing = [a for a in self.settings.distractions if a in open_now]
        for app in closing:
            await ex.call("apps_quit", {"app": app}, turn)
        await ex.call("system_volume", {"level": 15}, turn)
        self._focus_turn = turn.id
        self.audit.append("focus", minutes=minutes, closed=closing)
        n = len(closing)
        en = f"Focus for {minutes} minutes. I closed {n} distracting app{'' if n == 1 else 's'}. I'll call you when it's done."
        ta = f"{minutes} நிமிடம் focus. {n} app மூடிட்டேன். முடிஞ்சதும் சொல்றேன்."
        await self.speak(ta if lang == "ta" else en, lang)
        await self.hub.emit(TurnDone(ok=True))
        self._focus = asyncio.create_task(self._focus_timer(minutes * 60, lang))

    async def _focus_timer(self, total: int, lang: Lang, tick: float = 30) -> None:
        left = total
        while left > 0:
            await self.hub.emit(FocusState(remaining=left, total=total))
            step = min(tick, left)
            await asyncio.sleep(step)
            left -= int(step) or left
        await self.hub.emit(FocusState(remaining=0, total=total))
        await self._end_focus()
        await self.speak(
            "நேரம் முடிஞ்சது! Break எடுங்க." if lang == "ta" else "Focus time is over. Take a break!",
            lang,
        )

    async def _end_focus(self) -> None:
        tid, self._focus_turn = self._focus_turn, None
        if tid:
            ctx = ToolContext(tid, self.journal, self.holding, self.runner)
            ok, items = await undo_turn(self.journal, tid, ctx)
            self.audit.append("focus_end", ok=ok, restored=items)

    async def stop_focus(self, silent: bool = False) -> None:
        if self._focus and not self._focus.done():
            self._focus.cancel()
        await self.hub.emit(FocusState(remaining=0, total=0))
        await self._end_focus()
        if not silent:
            await self.speak("Focus stopped. Everything's back.", "en")
            await self.hub.emit(TurnDone(ok=True))

    async def _single_shot(self, messages: list[dict[str, Any]], images: int = 0) -> str | None:
        """One AI call without tools. Speaks the reason and returns None if it can't."""
        if not self.brain_ready:
            await self.speak("I need my AI brain for that. Add a free key in Settings.", "en")
            return None
        client = await self._client()
        try:
            sent = sum(
                len(str(m.get("content")))
                for m in messages
                if not isinstance(m.get("content"), list)
            )
            sent += sum(
                len(p.get("text", ""))
                for m in messages
                if isinstance(m.get("content"), list)
                for p in m["content"]
            )
            out = await assist.ask(client, messages)
            await self.hub.emit(Privacy(provider=client.spec.label, chars=sent, images=images))
            return out
        except LLMError as e:
            await self.hub.emit(ErrorEvent(code="brain", message=str(e)))
            await self.speak(str(e), "en")
            return None
        finally:
            await client.aclose()

    async def set_translate(self, on: bool) -> None:
        self.translating = on
        self.audit.append("translate_mode", on=on)
        await self.hub.emit(TranslateMode(on=on))
        if self.voice:
            self.voice.follow_timeout = 60.0 if on else 6.0
            self.voice.follow_up = on
        await self.speak(
            "Translator on. Speak Tamil and I'll say it in English, or the other way round. Say stop translating when done."
            if on
            else "Translator off.",
            "en",
        )
        await self.hub.emit(TurnDone(ok=True))

    async def translate_turn(self, text: str, lang: Lang) -> None:
        await self.hub.emit(Transcript(text=text, lang=lang))
        await self.hub.emit(Thinking())
        target = assist.target_for(text, lang)
        out = await self._single_shot(assist.translate_messages(text, target))
        if out:
            self.audit.append("translate", target=target, chars=len(text))
            await self.speak(out, "ta" if target == "ta" else "en")
        if self.voice:
            self.voice.follow_up = True
            self.voice.follow_timeout = 60.0
        await self.hub.emit(TurnDone(ok=bool(out)))

    async def translate_clipboard(self, target: str) -> None:
        turn = Turn(id=uuid.uuid4().hex[:12], lang="en", role=self._role)
        ex = self._executor()
        got = await self.runner(["pbpaste"], 5, None)
        text = got.out.strip()[:4000]
        if not text:
            await self.speak("Your clipboard is empty.", "en")
            await self.hub.emit(TurnDone(ok=False))
            return
        out = await self._single_shot(assist.translate_messages(text, target))
        if out:
            await ex.call("clipboard_set", {"text": out}, turn)
            await self.speak(
                "Done. The translation is on your clipboard."
                if target == "en"
                else "முடிஞ்சது. Clipboard-ல தமிழ்ல இருக்கு.",
                "ta" if target == "ta" else "en",
            )
            actions = self.journal.pending(turn.id)
            if actions:
                await self.hub.emit(
                    UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
                )
        await self.hub.emit(TurnDone(ok=bool(out)))

    async def explain_screen(self, question: str, lang: Lang) -> None:
        import tempfile
        from pathlib import Path

        await self.hub.emit(Transcript(text=question, lang=lang))
        if self.settings.provider not in assist.VISION_PROVIDERS:
            await self.speak(
                "Looking at the screen needs Gemini or Claude. Switch in Settings.", "en"
            )
            await self.hub.emit(TurnDone(ok=False))
            return
        await self.hub.emit(Thinking())
        with tempfile.TemporaryDirectory() as d:
            shot = Path(d) / "screen.png"
            await self.runner(["screencapture", "-x", "-t", "png", str(shot)], 10, None)
            png = shot.read_bytes() if shot.exists() else b""
        if not png:
            await self.speak("I couldn't take a screenshot. Allow Screen Recording for Sasu.", "en")
            await self.hub.emit(TurnDone(ok=False))
            return
        self.audit.append("screen_explain", bytes=len(png))
        out = await self._single_shot(assist.screen_messages(png, question, lang), images=1)
        if out:
            await self.speak(out, "ta" if assist.TAMIL.search(out) else lang)
        await self.hub.emit(TurnDone(ok=bool(out)))

    # ── scheduled tasks ────────────────────────────────────────────────────
    def _source(self, guest: bool = False) -> str:
        return "guest" if guest else "schedule" if self._unattended else "owner"

    async def add_task(self, task: tasks.Task, text: str, lang: Lang) -> None:
        await self.hub.emit(Transcript(text=text, lang=lang))
        self.tasks.add(task)
        self.audit.append("task", id=task.id, action="add", when=tasks.when(task))
        await self.hub.emit(TaskState(id=task.id, state="done", summary="scheduled"))
        await self._say_turn(
            f"சரி. {tasks.when(task)}: “{task.request}”."
            if lang == "ta"
            else f"Okay. {tasks.when(task)} I'll do: “{task.request}”.",
            lang,
        )

    async def run_task(self, task: tasks.Task) -> None:
        """An unattended run: safe steps happen, anything needing a yes waits for the owner."""
        self._unattended, self._blocked, self._last_said = task.id, None, ""
        self.audit.append("task", id=task.id, action="run", source="schedule")
        await self.hub.emit(TaskState(id=task.id, state="running", summary=task.request))
        state = "done"
        try:
            self.start_text_turn(task.request, role="owner")
            if self._turn is not None:
                await asyncio.wait({self._turn})  # a cancelled run must not stop the scheduler
                if self._turn.cancelled():
                    state = "failed"
        except Exception:  # noqa: BLE001 — a broken task must not stop the scheduler
            state = "failed"
        finally:
            self._unattended = None
        summary = self._last_said[:300]
        if self._blocked:
            state, summary = "needs_you", f"Waiting for your yes: {self._blocked}"
            self._needs_you = task.id
            await self._notify(f"Sasu needs you: {task.request}. Say “Sasu, run it”.")
        task.last_day = time.strftime("%Y-%m-%d", time.localtime(self.clock()))
        task.last_state, task.last_summary = state, summary
        self.tasks.update(task)
        self.audit.append("task", id=task.id, action=state)
        await self.hub.emit(TaskState(id=task.id, state=state, summary=summary))  # type: ignore[arg-type]

    async def run_task_now(self, tid: str) -> None:
        """The owner is here: run it as a normal turn, questions and all."""
        task = self.tasks.get(tid)
        if self._needs_you == tid:
            self._needs_you = None
        if task is None:
            return
        self.audit.append("task", id=tid, action="run", source="owner")
        await self.hub.emit(TaskState(id=tid, state="running", summary=task.request))
        self.start_text_turn(task.request, role="owner")
        if self._turn is not None:
            await asyncio.wait({self._turn})
        task.last_state, task.last_summary = "done", self._last_said[:300]
        self.tasks.update(task)
        await self.hub.emit(TaskState(id=tid, state="done", summary=task.last_summary))

    async def tasks_tick(self) -> None:
        for task in self.tasks.all():
            if tasks.due(task, self.clock()):
                await self.run_task(task)

    async def _watch_tasks(self) -> None:
        while True:
            await asyncio.sleep(30)
            if not self.locked and not (self._turn and not self._turn.done()):
                await self.tasks_tick()

    # ── watch & tell ───────────────────────────────────────────────────────
    async def start_watch(self, req: watch.Request, text: str, lang: Lang) -> None:
        ta = lang == "ta"
        await self.hub.emit(Transcript(text=text, lang=lang))
        if len(self.watches) >= watch.MAX_WATCHES:
            return await self._say_turn(
                "ஏற்கனவே 10 விஷயம் பார்த்துட்டு இருக்கேன்." if ta else "I'm already watching 10 things.",
                lang,
                ok=False,
            )
        label, ready = await self._watch_label(req, lang)
        if label is None:
            return await self._say_turn(ready, lang, ok=False)
        w = watch.Watch(req.kind, label)
        task = asyncio.create_task(self._run_watch(w, req, ready, lang))
        self.watches[w.id] = (w, task)
        self.audit.append("watch", id=w.id, watch=w.kind, state="started")
        await self.hub.emit(WatchState(id=w.id, kind=w.kind, label=label, state="started"))
        await self._say_turn(
            f"சரி, {label} முடிஞ்சதும் சொல்றேன்." if ta else f"Okay, I'll tell you: {label}.", lang
        )

    async def _watch_label(self, req: watch.Request, lang: Lang) -> tuple[str | None, str]:
        """(label, setup) for a new watch, or (None, why it can't start)."""
        from .tools.runtime import applescript

        ta = lang == "ta"
        if req.kind == "download":
            parts = watch.partials(self.home / "Downloads")
            if not parts:
                return None, (
                    "இப்போ எந்த download-உம் ஓடல." if ta else "I don't see a download running."
                )
            name = sorted(parts)[0].rsplit(".", 1)[0]
            return f"download {name}", ""
        if req.kind == "battery":
            now = watch.battery_percent((await self.runner(["pmset", "-g", "batt"], 5, None)).out)
            if now is None:
                return None, "I can't read the battery on this Mac."
            return f"battery at {req.level}%", "up" if req.level >= now else "down"
        if req.kind == "file":
            got = await self.runner(
                applescript(
                    'tell application "Finder" to set s to selection',
                    'if s is {} then return ""',
                    "return POSIX path of (item 1 of s as alias)",
                ),
                8,
                None,
            )
            path = got.out.strip()
            if not path or not Path(path).is_file():
                return None, (
                    "Finder-ல file-ஐ select பண்ணுங்க." if ta else "Select the file in Finder first."
                )
            return f"{Path(path).name} changes", path
        if req.kind == "page":
            url = await self._front_url()
            if not url:
                return None, (
                    "Safari அல்லது Chrome-ல page-ஐ திறங்க."
                    if ta
                    else "Open the page in Safari or Chrome first."
                )
            host = url.split("/")[2] if "://" in url else url
            return (f"price drop on {host}" if req.price else f"{host} changes"), url
        return f"“{req.command[:60]}” finishes", req.command

    async def _front_url(self) -> str:
        from .tools.runtime import applescript

        front = (
            await self.runner(
                applescript(
                    'tell application "System Events" to return name of first process whose frontmost is true'
                ),
                5,
                None,
            )
        ).out.strip()
        scripts = {
            "Safari": 'tell application "Safari" to return URL of current tab of front window',
            "Google Chrome": 'tell application "Google Chrome" to return URL of active tab of front window',
            "Brave Browser": 'tell application "Brave Browser" to return URL of active tab of front window',
            "Microsoft Edge": 'tell application "Microsoft Edge" to return URL of active tab of front window',
            "Arc": 'tell application "Arc" to return URL of active tab of front window',
        }
        if front not in scripts:
            return ""
        return str((await self.runner(applescript(scripts[front]), 5, None)).out).strip()

    async def _run_watch(self, w: watch.Watch, req: watch.Request, setup: str, lang: Lang) -> None:
        ta = lang == "ta"
        every = self.watch_every
        try:
            if req.kind == "download":
                folder = self.home / "Downloads"
                while watch.partials(folder):
                    await asyncio.sleep(every["download"])
                done = watch.newest_file(folder)
                size = -1
                while done is not None and done.exists() and done.stat().st_size != size:
                    size = done.stat().st_size
                    await asyncio.sleep(every["download"])
                name = done.name if done else "your download"
                msg = f"Download முடிஞ்சது: {name}." if ta else f"Your download finished: {name}."
            elif req.kind == "battery":
                while True:
                    out = (await self.runner(["pmset", "-g", "batt"], 5, None)).out
                    pct = watch.battery_percent(out)
                    if pct is not None and (
                        pct >= req.level if setup == "up" else pct <= req.level
                    ):
                        break
                    await asyncio.sleep(every["battery"])
                msg = f"Battery {pct}% ஆச்சு." if ta else f"Battery is at {pct}%."
            elif req.kind == "file":
                path = Path(setup)
                start = path.stat().st_mtime
                while path.exists() and path.stat().st_mtime == start:
                    await asyncio.sleep(every["file"])
                msg = f"{path.name} மாறிடுச்சு." if ta else f"{path.name} just changed."
            elif req.kind == "page":
                first = await watch.fetch(setup, self.transport)
                if first is None:
                    raise RuntimeError("page")
                base_price = watch.first_price(first) if req.price else None
                base = watch.fingerprint(first)
                while True:
                    await asyncio.sleep(every["page"])
                    text = await watch.fetch(setup, self.transport)
                    if text is None:
                        continue
                    if base_price is not None:
                        price = watch.first_price(text)
                        if price is not None and price < base_price:
                            msg = (
                                f"விலை குறைஞ்சிருக்கு: {base_price:g} → {price:g}."
                                if ta
                                else f"Price dropped from {base_price:g} to {price:g}."
                            )
                            break
                    elif watch.fingerprint(text) != base:
                        msg = "Page மாறிடுச்சு." if ta else "The page changed."
                        break
            else:
                turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role="owner")
                result = await self._executor().call(
                    "shell_run", {"command": setup, "minutes": 60}, turn
                )
                ok = result.startswith("OK")
                last = [
                    ln for ln in result.splitlines()[1:] if ln.strip() and "untrusted>" not in ln
                ]
                tail = last[-1][:120] if last and not ok else ""
                if ok:
                    msg = (
                        f"“{setup[:40]}” முடிஞ்சது, pass."
                        if ta
                        else f"“{setup[:40]}” finished fine."
                    )
                else:
                    msg = (
                        f"“{setup[:40]}” fail ஆச்சு. {tail}"
                        if ta
                        else f"“{setup[:40]}” failed. {tail}"
                    ).strip()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a broken watch must not take the core down
            msg = (
                "I stopped watching: something went wrong."
                if not ta
                else "பார்க்க முடியல, நிறுத்திட்டேன்."
            )
        self.watches.pop(w.id, None)
        while self._turn and not self._turn.done():  # never talk over a reply in progress
            await asyncio.sleep(0.2)
        self.audit.append("watch", id=w.id, watch=w.kind, state="fired")
        await self.hub.emit(WatchState(id=w.id, kind=w.kind, label=w.label, state="fired"))
        await self._notify(msg)
        await self.speak(msg, lang)

    async def _notify(self, text: str) -> None:
        from .tools.runtime import applescript

        await self.runner(
            applescript('display notification (item 1 of argv) with title "Sasu"') + [text], 5, None
        )

    async def stop_watches(self, lang: Lang) -> None:
        n = len(self.watches)
        for wid in list(self.watches):
            self.cancel_watch(wid)
        await self._say_turn(
            (
                f"{n} watch நிறுத்திட்டேன்."
                if lang == "ta"
                else f"Stopped {n} watch{'es' if n != 1 else ''}."
            )
            if n
            else ("எதுவும் பார்க்கல." if lang == "ta" else "I'm not watching anything."),
            lang,
        )

    def cancel_watch(self, wid: str) -> bool:
        item = self.watches.pop(wid, None)
        if item is None:
            return False
        w, task = item
        task.cancel()
        self.audit.append("watch", id=w.id, watch=w.kind, state="stopped")
        self._bg = asyncio.create_task(
            self.hub.emit(WatchState(id=w.id, kind=w.kind, label=w.label, state="stopped"))
        )
        return True

    async def list_watches(self, lang: Lang) -> None:
        labels = [w.label for w, _ in self.watches.values()]
        if not labels:
            text = "இப்போ எதுவும் பார்க்கல." if lang == "ta" else "I'm not watching anything right now."
        else:
            text = (
                ("பார்த்துட்டு இருக்கேன்: " if lang == "ta" else "I'm watching: ")
                + "; ".join(labels)
                + "."
            )
        await self._say_turn(text, lang)

    async def tidy_turn(self, where: str, text: str, lang: Lang) -> None:
        """Sort Desktop / Downloads: plan → one yes → the normal file tools (undoable)."""
        from .protocol import PlanPreview

        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role=self._role)
        self.audit.append("command", source=self._source(), text=text, turn=turn.id, fast="tidy")
        await self.hub.emit(Transcript(text=text, lang=lang))
        await self.hub.emit(Thinking())
        folder = self.home / where
        plan = await asyncio.to_thread(tidy.plan_for, folder) if folder.is_dir() else None
        if plan is None or plan.count == 0:
            await self.speak(
                f"{where} ஏற்கனவே சுத்தமா இருக்கு!" if lang == "ta" else f"{where} is already tidy.",
                lang,
            )
            await self.hub.emit(TurnDone(ok=True))
            return
        await self.hub.emit(PlanPreview(id=turn.id, steps=tidy.steps(plan, lang)))
        ask = (
            f"{where}-ல {plan.count} file ஒழுங்கு படுத்தட்டுமா?"
            if lang == "ta"
            else f"Tidy {plan.count} files in {where}?"
        )
        if not await self.approve(ask, "confirm", lang, False):
            await self.speak(
                "சரி, எதுவும் மாத்தல." if lang == "ta" else "Okay, I left it as it is.", lang
            )
            await self.hub.emit(TurnDone(ok=False))
            return
        turn.plan_approved = True
        ex = self._executor()
        ok = True
        for name, args in tidy.calls(plan):
            ok = (await ex.call(name, args, turn)).startswith("OK") and ok
        await self.speak(tidy.summary(plan, lang), lang)
        actions = self.journal.pending(turn.id)
        if actions:
            await self.hub.emit(
                UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
            )
        await self.hub.emit(TurnDone(ok=ok))

    async def tell_joke(self, lang: Lang) -> None:
        await self.hub.emit(Fun(kind="joke"))
        await self.speak(joke(lang), lang)
        await self.hub.emit(TurnDone(ok=True))

    async def on_alarm(self, kind: str, detail: str) -> None:
        if kind == "canary":
            await self.request_snap("trap file")
            await self.lock("canary")
            await self.siren("a trap file was touched")

    async def fast_turn(
        self, text: str, fast: fastpath.Fast, lang: Lang, *, guest: bool = False
    ) -> None:
        """Common requests, done locally in about a second."""
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, guest=guest, role=self._role)
        self.audit.append(
            "command", source=self._source(guest), text=text, turn=turn.id, fast=fast.kind
        )
        await self.hub.emit(Transcript(text=text, lang=lang))
        ex = self._executor()
        ok = True
        content = ""
        for name, args in fast.calls:
            result = await ex.call(name, args, turn)
            ok = ok and result.startswith("OK")
            content += result
        if not ok:
            if guest and "BLOCKED" in content:
                reply = (
                    "Sorry, only my owner can do that."
                    if lang != "ta"
                    else "மன்னிக்கவும், என் owner மட்டும் தான் இதை செய்ய முடியும்."
                )
            else:
                reply = "That didn't work." if lang != "ta" else "அது சரியா வேலை செய்யல."
        elif fast.kind == "battery":
            reply = fastpath.battery_reply(content, lang)
        else:
            reply = fast.say_ta if lang == "ta" else fast.say_en
        self.last_calls = turn.calls or self.last_calls
        await self.speak(reply, lang)
        actions = self.journal.pending(turn.id)
        if actions:
            await self.hub.emit(
                UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
            )
        await self.hub.emit(TurnDone(ok=ok))

    async def _no_brain(self, text: str) -> None:
        lang = detect_lang(text)
        await self.hub.emit(Transcript(text=text, lang=lang))
        await self.hub.emit(
            ErrorEvent(code="no_brain", message="Add a free AI key in Settings → AI brain.")
        )
        say = "I need my AI brain for that. Add a free key in Settings."
        await self.speak(say if lang != "ta" else "இதுக்கு AI key வேணும். Settings-ல சேர்க்கவும்.", lang)
        await self.hub.emit(TurnDone(ok=False))

    async def speak(self, text: str, lang: Lang, big: bool | None = None) -> None:
        """Streams the caption word by word while the Mac voice speaks it.
        Amma mode (an elder speaking, or a care reminder): large captions, slower voice."""
        words = text.split(" ")
        self._last_said = text
        elder = self._role == "elder" if big is None else big
        self.speaker.rate = 150 if elder else 195
        voice = asyncio.create_task(self._say(text)) if self.settings.tts else None
        await self.hub.emit(SayStart(text=words[0], lang=lang, big=elder))
        for w in words[1:]:
            await asyncio.sleep((0.1 if elder else 0.07) if voice else 0.03)
            await self.hub.emit(SayChunk(text=" " + w))
        if voice:
            await voice
        await self.hub.emit(SayEnd())

    async def _say(self, text: str) -> None:
        """Half-duplex: while Sasu talks, the mic only listens for "stop"."""
        if self.voice:
            self.voice.set_speaking(True)
        try:
            await self.speaker.say(text)
        finally:
            if self.voice:
                self.voice.set_speaking(False)

    def _executor(self) -> Executor:
        return Executor(
            self.hub.emit, self.approve, self.audit, self.journal, self.holding, self.runner,
            canaries=self.canaries, on_alarm=self.on_alarm,
        )  # fmt: skip

    async def _client(self) -> ChatClient:
        spec = SPECS[self.settings.provider]
        key = self.keys.get(spec.id)
        model = self.models.get(spec.id)
        if model is None:
            probe = ChatClient(spec, key, spec.default_model, self.transport)
            model = pick_model(spec, await probe.list_models(), self.settings.model)
            await probe.aclose()
            self.models[spec.id] = model
            await self.hub.emit(self.brain_status())
        return ChatClient(spec, key, model, self.transport)

    async def agent_turn(self, text: str, *, guest: bool = False, lang: Lang | None = None) -> None:
        lang = lang or detect_lang(text)
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, guest=guest, role=self._role)
        self.audit.append("command", source=self._source(guest), text=text, turn=turn.id)
        await self.hub.emit(Transcript(text=text, lang=lang))
        await self.hub.emit(Thinking())
        client = await self._client()
        ok = True
        try:
            agent = Agent(client, self._executor(), self.hub.emit, fun=self.settings.fun_replies)
            if turn.role == "elder":
                agent.context = (
                    "\nThe speaker is an elderly family member. Reply warmly in simple Tamil (Tamil script) "
                    "unless they spoke English; one short sentence."
                )
            if turn.role == "owner" and not guest:
                facts = self.memory.all()[-20:]
                if facts:
                    agent.context = (
                        "\nThings the user asked you to remember (use when relevant):\n"
                        + "\n".join(f"- {f.text}" for f in facts)
                    )
            reply = await agent.run(text, turn, list(self.history))
        except LLMError as e:
            ok, reply = False, str(e)
        finally:
            await client.aclose()
            await self.hub.emit(Privacy(provider=client.spec.label, chars=turn.sent_chars))

        reply_lang: Lang = "ta" if detect_lang(reply) == "ta" else lang
        if ok:
            self.history.extend(
                [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
            )
            if turn.calls:
                self.last_calls = turn.calls
            await self.speak(reply, reply_lang)
        else:
            await self.hub.emit(ErrorEvent(code="brain", message=reply))
            await self.speak(reply, "en")
        actions = self.journal.pending(turn.id)
        if actions:
            await self.hub.emit(
                UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
            )
        await self.hub.emit(TurnDone(ok=ok))

    async def undo(self, turn_id: str | None) -> None:
        tid = turn_id or self.journal.last_turn()
        if tid is None:
            await self.speak("There's nothing to undo.", "en")
            await self.hub.emit(TurnDone(ok=True))
            return
        ctx = ToolContext(tid, self.journal, self.holding, self.runner)
        ok, items = await undo_turn(self.journal, tid, ctx)
        summary = "; ".join(items) or "nothing to undo"
        self.audit.append("undo", turn=tid, ok=ok, summary=summary)
        await self.hub.emit(Undone(turn_id=tid, ok=ok, summary=summary))
        await self.speak(f"Undone: {summary}." if ok else f"Partly undone: {summary}.", "en")
        await self.hub.emit(TurnDone(ok=ok))

    async def save_skill(self, name: str) -> None:
        if not self.last_calls:
            await self.speak("I haven't done anything yet to save.", "en")
            await self.hub.emit(TurnDone(ok=False))
            return
        key = self.skills.save(name, self.last_calls)
        self.audit.append("skill_saved", name=key, steps=len(self.last_calls))
        await self.speak(f"Saved. Say “{key}” any time.", "en")
        await self.hub.emit(TurnDone(ok=True))

    async def run_skill(self, name: str) -> None:
        from .protocol import PlanPreview

        calls = self.skills.get(name) or []
        turn = Turn(id=uuid.uuid4().hex[:12], lang="en")
        ex = self._executor()
        await self.hub.emit(Transcript(text=name, lang="en"))
        await self.hub.emit(PlanPreview(id=turn.id, steps=[f"{c['tool']}" for c in calls]))
        if not await self.approve(f"Run “{name}” ({len(calls)} steps)?", "confirm", "en", False):
            await self.hub.emit(TurnDone(ok=False))
            return
        turn.plan_approved = True
        for c in calls:
            await ex.call(c["tool"], c["args"], turn)
        await self.speak(f"Done: {name}.", "en")
        actions = self.journal.pending(turn.id)
        if actions:
            await self.hub.emit(
                UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
            )
        await self.hub.emit(TurnDone(ok=True))

    # ── voice ──────────────────────────────────────────────────────────────
    async def _watch_away(self) -> None:
        """Lock while the owner is away from the keyboard (opt-in: away_minutes > 0)."""
        from .tools.runtime import run

        while True:
            await asyncio.sleep(20)
            minutes = self.settings.away_minutes
            if minutes <= 0:
                if "away" in self.locks:
                    await self.unlock("away")
                continue
            p = await run(["ioreg", "-c", "IOHIDSystem", "-d", "4"], 5)
            idle = idle_seconds(p.out)
            if idle is None:
                continue
            if idle > minutes * 60 and "away" not in self.locks:
                await self.lock("away")
            elif idle < 10 and "away" in self.locks:
                await self.unlock("away")

    async def _watch_music(self) -> None:
        """The robot dances while Spotify or Music plays, and knows the song."""
        from .tools.runtime import applescript, run

        script = applescript(
            'set out to ""',
            'if application "Spotify" is running then tell application "Spotify" to if player state is playing then set out to (name of current track) & " — " & (artist of current track)',
            'if out is "" and application "Music" is running then tell application "Music" to if player state is playing then set out to (name of current track) & " — " & (artist of current track)',
            "return out",
        )
        current = ""
        while True:
            await asyncio.sleep(4)
            p = await run(script, 5)
            song = p.out.strip() if p.ok else ""
            if song != current:
                current = song
                await self.hub.emit(Fun(kind="dance", on=bool(song), detail=song[:120]))

    async def set_voice(self, **changes: Any) -> None:
        profiles = self.vault.load_profiles()
        self.voice_state = self.voice_state.model_copy(
            update={
                "enrolled": any(p.role == "owner" for p in profiles),
                "profiles": [f"{p.name} ({p.role})" for p in profiles],
                **changes,
            }
        )
        await self.hub.emit(self.voice_state)

    async def boot(self) -> None:
        """Start listening if the voice models are already on disk, and the watchers."""
        self._watchers = [
            asyncio.create_task(self._watch_away()),
            asyncio.create_task(self._watch_music()),
            asyncio.create_task(self._watch_nudges()),
            asyncio.create_task(self._watch_clipboard()),
            asyncio.create_task(self._watch_care()),
            asyncio.create_task(self._watch_tasks()),
        ]
        if voice_models.ready(self.models_dir):
            await self.start_voice()
        else:
            await self.set_voice(state="missing")

    async def start_voice(self) -> None:
        if self.voice:
            return
        await self.set_voice(state="loading", detail="Loading voice models…")
        loop = asyncio.get_running_loop()
        try:
            pipeline = await loop.run_in_executor(
                None, VoicePipeline, self.models_dir, CoreVoice(self), loop
            )
            pipeline.start()
        except Exception as e:  # mic permission denied, broken model…
            await self.set_voice(state="error", detail=f"Microphone or model problem: {e}")
            return
        self.voice = pipeline
        self.audit.append("voice", state="listening")
        await self.set_voice(state="listening", detail="Listening for “Hey Sasu”", progress=1.0)

    async def setup_voice(self) -> None:
        loop = asyncio.get_running_loop()
        last = 0.0

        def progress(done: int, total: int, model: str) -> None:
            nonlocal last
            frac = done / total
            if frac - last >= 0.01 or done == total:
                last = frac
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        self.set_voice(state="downloading", progress=frac, detail=model)
                    )
                )

        await self.set_voice(state="downloading", progress=0.0, detail="starting")
        try:
            await loop.run_in_executor(None, voice_models.download_all, self.models_dir, progress)
        except Exception as e:
            await self.set_voice(state="error", detail=f"Download failed: {e}")
            return
        self.audit.append("voice", state="downloaded")
        await self.start_voice()

    async def voice_command(self, heard: Heard) -> None:
        if self.locked:
            self.audit.append("rejected", reason="locked", command="voice")
            await self.speak("I'm locked right now.", "en")
            return
        import time as _time

        lang: Lang = "ta" if heard.lang == "ta" else "en"
        self.last_lang = lang
        role = "owner"
        profiles = self.vault.load_profiles()
        recently = _time.monotonic() - self.owner_verified_at < 60
        if profiles:
            who, score = identify(profiles, heard.embedding) if heard.embedding else (None, 0.0)
            if who is not None:
                self.owner_verified_at = _time.monotonic()
                self._last_speaker = (who.name, who.role)
                role = who.role
            elif heard.embedding is None and recently:
                role = self._last_speaker[1]  # too short to check; same person moments ago
            elif heard.embedding is None:
                await self.speak(
                    "Sorry, say that again?" if lang != "ta" else "மறுபடியும் சொல்லுங்க?", lang
                )
                if self.voice:
                    self.voice.arm()
                return
            else:
                self.intruders_unseen.append(heard.text)
                self.audit.append("intruder", text=heard.text, score=score)
                await self.hub.emit(
                    Intruder(text=heard.text, score=score, count=len(self.intruders_unseen))
                )
                await self.request_snap("stranger")
                if self.settings.guest_mode == "reject":
                    await self.reject_speaker(score)
                    await self.hub.emit(
                        ErrorEvent(code="not_owner", message="Sorry, I only listen to my owner.")
                    )
                    await self.speak("Sorry, I only listen to my owner.", "en")
                    await self.hub.emit(TurnDone(ok=False))
                    return
                self.audit.append("guest", score=score)
                await self.note_stranger()
                role = "guest"
        if self.voice:
            self.voice.follow_up = True  # keep listening after the reply, no wake word needed
        self.audit.append(
            "speaker", name=self._last_speaker[0] if role != "guest" else "guest", role=role
        )
        self.start_text_turn(heard.text, guest=role == "guest", lang=lang, role=role)

    async def request_snap(self, reason: str) -> None:
        """Ask the overlay for one camera photo (opt-in). Upload is accepted for 20 s."""
        import time as _time

        if not self.settings.intruder_photo:
            return
        sid = uuid.uuid4().hex[:16]
        now = _time.monotonic()
        self.snaps = {k: v for k, v in self.snaps.items() if v > now}
        self.snaps[sid] = now + 20
        await self.hub.emit(SnapRequest(id=sid, reason=reason))

    def accept_photo(self, sid: str, jpeg: bytes, reason: str = "") -> str | None:
        """Store a requested intruder photo. Returns the file name, or None if refused."""
        import os
        import time as _time

        if self.snaps.pop(sid, 0) < _time.monotonic():
            return None
        if not (1000 < len(jpeg) <= 400_000) or jpeg[:3] != b"\xff\xd8\xff":
            return None
        self.photos_dir.mkdir(exist_ok=True)
        os.chmod(self.photos_dir, 0o700)
        name = _time.strftime("%Y%m%d-%H%M%S") + f"-{sid[:6]}.jpg"
        path = self.photos_dir / name
        path.write_bytes(jpeg)
        os.chmod(path, 0o600)
        self.audit.append("intruder_photo", file=name, bytes=len(jpeg))
        return name

    async def voice_type(self, text: str, lang: Lang) -> None:
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role=self._role)
        await self.hub.emit(Transcript(text=text, lang=lang))
        result = await self._executor().call("type_text", {"text": text}, turn)
        ok = result.startswith("OK")
        await self.speak(
            ("Typed." if lang != "ta" else "டைப் பண்ணிட்டேன்.") if ok else "I couldn't type that.", lang
        )
        await self.hub.emit(TurnDone(ok=ok))

    async def read_aloud(self) -> None:
        from .tools import ToolContext as Ctx
        from .tools.keyboard import selected_text

        text = await selected_text(Ctx("read", self.journal, self.holding, self.runner))
        if not text:
            await self.speak("Select some text first, then ask me to read it.", "en")
            await self.hub.emit(TurnDone(ok=False))
            return
        self.audit.append("read_aloud", chars=len(text))
        text = text[:3000]
        await self.speak(text, "ta" if assist.TAMIL.search(text) else "en")
        await self.hub.emit(TurnDone(ok=True))

    async def festival_greeting(self) -> bool:
        """Once per festival day, the first wake gets a festive hello."""
        import datetime as dt

        f = extras.festival()
        today = dt.date.today().isoformat()
        if not (self.settings.festivals and f) or self._greeted_festival == today:
            return False
        self._greeted_festival = today
        await self.hub.emit(Fun(kind="festival", detail=f[0]))
        await self._say(f[2] if self.last_lang == "ta" else f[1])
        return True

    async def _watch_nudges(self) -> None:
        """Opt-in nudges: low battery, a meeting in five minutes."""
        import re as _re

        from .tools.runtime import applescript, run

        warned_batt = False
        warned_events: set[str] = set()
        soon = applescript(
            "set out to {}",
            "set t0 to current date",
            "set t1 to t0 + (6 * minutes)",
            'tell application "Calendar"',
            "repeat with c in calendars",
            "repeat with e in (every event of c whose start date > t0 and start date < t1)",
            "set end of out to summary of e",
            "end repeat",
            "end repeat",
            "end tell",
            "set AppleScript's text item delimiters to linefeed",
            "return out as text",
        )
        while True:
            await asyncio.sleep(60)
            if not self.settings.nudges or self.locked or (self._turn and not self._turn.done()):
                continue
            batt = (await run(["pmset", "-g", "batt"], 5)).out
            m = _re.search(r"(\d+)%;\s*discharging", batt)
            if m and int(m.group(1)) <= 15 and not warned_batt:
                warned_batt = True
                await self.speak(f"Battery is at {m.group(1)} percent. Time to plug in.", "en")
            elif not m:
                warned_batt = False
            for title in (await run(soon, 8)).out.splitlines():
                if title.strip() and title not in warned_events:
                    warned_events.add(title)
                    await self.hub.emit(Fun(kind="briefing"))
                    await self.speak(f"Heads up: {title} starts in five minutes.", "en")

    async def _say_turn(self, text: str, lang: Lang, ok: bool = True) -> None:
        await self.speak(text, lang)
        await self.hub.emit(TurnDone(ok=ok))

    # ── meeting notes ──────────────────────────────────────────────────────
    async def start_meeting(self, lang: Lang) -> None:
        import time as _t

        if not self.voice:
            await self._say_turn("Turn on voice first, then I can take meeting notes.", "en", False)
            return
        await self.speak(
            "Taking notes. Say stop meeting when you're done."
            if lang != "ta"
            else "Notes எடுக்கறேன். முடிஞ்சதும் meeting முடிஞ்சதுன்னு சொல்லுங்க.",
            lang,
        )
        self.meeting, self._meeting_started, self._meeting_lang = [], _t.time(), lang
        self.voice.set_meeting(True)
        self.audit.append("meeting", state="start")
        await self.hub.emit(MeetingState(on=True))
        await self.hub.emit(TurnDone(ok=True))

    async def meeting_caption(self, text: str, lang: str) -> None:
        import time as _t

        if self.meeting is None:
            return
        if lifelog.MEETING_STOP.search(text):
            self._start(self.end_meeting())
            return
        self.meeting.append(text)
        await self.hub.emit(Caption(text=text, lang="ta" if lang == "ta" else "en"))
        await self.hub.emit(
            MeetingState(
                on=True, seconds=int(_t.time() - self._meeting_started), lines=len(self.meeting)
            )
        )

    async def end_meeting(self) -> None:
        import time as _t

        lines, self.meeting = self.meeting or [], None
        if self.voice:
            self.voice.set_meeting(False)
        lang = self._meeting_lang
        secs = int(_t.time() - self._meeting_started)
        await self.hub.emit(MeetingState(on=False, seconds=secs, lines=len(lines)))
        self.audit.append("meeting", state="stop", seconds=secs, lines=len(lines))
        if not lines:
            await self._say_turn("Meeting stopped. I didn't hear anything to note.", "en")
            return
        await self.hub.emit(Thinking())
        transcript = "\n".join(lines)
        notes = (
            await self._single_shot(lifelog.meeting_messages(transcript, lang))
            if self.brain_ready
            else None
        )
        body = (notes + "\n\n— Transcript —\n" + transcript) if notes else transcript
        title = "Meeting notes " + _t.strftime(
            "%d %b %Y, %H:%M", _t.localtime(self._meeting_started)
        )
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role="owner")
        turn.plan_approved = True
        result = await self._executor().call("notes_add", {"title": title, "body": body}, turn)
        ok = result.startswith("OK")
        msg = (
            ("Saved the meeting notes in Notes." if notes else "Saved the transcript in Notes.")
            if ok
            else "I couldn't save to Notes."
        )
        await self.speak(
            msg
            if lang != "ta"
            else ("Meeting notes Notes-ல save பண்ணிட்டேன்." if ok else "Notes-ல save பண்ண முடியல."),
            lang,
        )
        actions = self.journal.pending(turn.id)
        if actions:
            await self.hub.emit(
                UndoAvailable(turn_id=turn.id, actions=[a.describe() for a in actions])
            )
        await self.hub.emit(TurnDone(ok=ok))

    # ── SOS and lost-Mac alarm ─────────────────────────────────────────────
    async def sos_turn(self, lang: Lang, help: bool = False) -> None:
        import time as _t

        contact = self.settings.sos_contact.strip()
        if not contact:
            await self.speak(
                "Set an emergency contact in Settings, Security first.", "en", big=help
            )
            return
        self._sos_cancel = cancel = asyncio.Event()
        delay = self.help_delay if help else self.sos_delay
        self.audit.append("alarm", alarm="help" if help else "sos", detail="countdown")
        if help:
            who = self._last_speaker[0]
            await self.hub.emit(Care(kind="help", who=who))
            await self.hub.emit(
                Alarm(kind="sos", detail=f"{who} asked for help. Calling family in 10 seconds.")
            )
            await self.speak(
                "Don't worry, I'm telling your family now. Say cancel if you're okay."
                if lang != "ta"
                else "பயப்படாதீங்க, உங்க குடும்பத்துக்கு சொல்றேன். சரியா இருந்தா cancel சொல்லுங்க.",
                lang,
                big=True,
            )
        else:
            await self.hub.emit(
                Alarm(kind="sos", detail="Sending SOS in 5 seconds. Say cancel to stop.")
            )
            await self._say(
                "Sending S O S in 5 seconds. Say cancel to stop."
                if lang != "ta"
                else "5 விநாடியில் SOS அனுப்பறேன். வேண்டாம்னா cancel சொல்லுங்க."
            )
        try:
            await asyncio.wait_for(cancel.wait(), delay)
            self._sos_cancel = None
            self.audit.append("alarm", alarm="sos", detail="cancelled")
            await self.speak("SOS cancelled." if lang != "ta" else "SOS ரத்து பண்ணிட்டேன்.", lang)
            return
        except TimeoutError:
            pass
        self._sos_cancel = None
        where = f" Last known area: {self.settings.city}." if self.settings.city else ""
        who = self._last_speaker[0] if self._last_speaker[0] != "Owner" else "the owner of this Mac"
        text = f"SOS from {who}, sent by Sasu at {_t.strftime('%H:%M, %d %b')}. I may need help, please call me.{where}"
        if help:
            text = f"Help needed: {self._last_speaker[0]} asked Sasu for help at {_t.strftime('%H:%M, %d %b')}. Please call.{where}"
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role="owner")
        turn.plan_approved = True
        result = await self._executor().call("messages_send", {"to": contact, "text": text}, turn)
        ok = result.startswith("OK")
        self.audit.append("alarm", alarm="sos", detail="sent" if ok else "failed")
        await self.speak(
            ("SOS sent." if ok else "I couldn't send the SOS. Please call for help.")
            if lang != "ta"
            else ("SOS அனுப்பிட்டேன்." if ok else "SOS அனுப்ப முடியல. உடனே call பண்ணுங்க."),
            lang,
        )

    async def note_stranger(self) -> None:
        import time as _t

        now = _t.time()
        self._strangers.append(now)
        if sum(1 for t in self._strangers if now - t < 600) >= 3:
            await self.siren("3 strangers tried to use Sasu")

    async def siren(self, reason: str) -> None:
        """Lost-Mac alarm (opt-in): loud siren, robot flashes red, screen locks."""
        if not self.settings.lost_alarm or self._siren_turn:
            return
        turn = Turn(id=uuid.uuid4().hex[:12], lang="en", role="owner")
        turn.plan_approved = True
        await self._executor().call("system_volume", {"level": 80}, turn)
        self._siren_turn = turn.id
        self.audit.append("alarm", alarm="siren", detail=reason)
        await self.hub.emit(Alarm(kind="siren", detail=reason))
        await self.runner(["pmset", "displaysleepnow"], 5, None)
        await self.lock("intruder")

    # ── diary ──────────────────────────────────────────────────────────────
    async def diary_add(self, text: str, lang: Lang) -> None:
        self.diary.add(text)
        self.audit.append("diary", action="add", chars=len(text))
        await self._say_turn("Saved in your diary." if lang != "ta" else "டைரில எழுதிட்டேன்.", lang)

    async def diary_summary(self, lang: Lang) -> None:
        import time as _t

        week = [e.text for e in self.diary.all() if e.at > _t.time() - 7 * 86400]
        if not week:
            await self._say_turn(
                "Your diary is empty this week." if lang != "ta" else "இந்த வாரம் டைரில எதுவும் இல்ல.",
                lang,
            )
            return
        await self.hub.emit(Thinking())
        recap = (
            await self._single_shot(lifelog.diary_messages(week, lang))
            if self.brain_ready
            else None
        )
        if not recap:
            recap = f"You wrote {len(week)} entries this week. The last one: {week[-1]}"
        await self._say_turn(recap, "ta" if assist.TAMIL.search(recap) else lang)

    # ── clipboard memory ───────────────────────────────────────────────────
    async def _watch_clipboard(self) -> None:
        last = ""
        while True:
            await asyncio.sleep(2)
            if not self.settings.clipboard_memory or self.locked:
                continue
            got = await self.runner(["pbpaste"], 3, None)
            clip = got.out.strip() if got.ok else ""
            if clip and clip != last:
                last = clip
                recent = self.clips.all()[-1:] if self.clips.path.exists() else []
                if lifelog.worth_keeping(clip) and not (recent and recent[0].text == clip):
                    self.clips.add(clip)

    async def clip_recall(self, text: str, lang: Lang) -> None:
        clips = self.clips.all() if self.clips.path.exists() else []
        if not clips:
            await self._say_turn(
                "I don't have any clipboard history. Turn on clipboard memory in Settings."
                if lang != "ta"
                else "Clipboard history இல்ல. Settings-ல on பண்ணுங்க.",
                lang,
                False,
            )
            return
        want_link = "link" in text.lower() or "லிங்க்" in text
        pool = [c for c in clips if lifelog.URL.search(c.text)] if want_link else clips
        hits = self.clips.search(text, limit=1) if not want_link else []
        best = (
            hits[0]
            if hits
            else (
                pool[-2]
                if len(pool) > 1 and pool[-1].text == clips[-1].text and not want_link
                else (pool[-1] if pool else clips[-1])
            )
        )
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role="owner")
        await self._executor().call("clipboard_set", {"text": best.text}, turn)
        desc = lifelog.describe_clip(best.text)
        await self._say_turn(
            f"You copied {desc}. It's back on your clipboard."
            if lang != "ta"
            else f"நீங்க copy பண்ணது {desc}. மறுபடி clipboard-ல வெச்சிட்டேன்.",
            lang,
        )

    # ── Amma mode ──────────────────────────────────────────────────────────
    def _voice_answer(self, text: str) -> bool:
        """A spoken "yes" / "no" answers a pending confirm question (never Touch ID ones)."""
        waiting = [
            pid for pid, p in self.pending.items() if p.kind == "confirm" and not p.future.done()
        ]
        if not waiting:
            return False
        t = text.strip().lower().rstrip(".!")
        if care.CONFIRM_YES.match(t) or re.match(
            r"^(?:ok|okay|sari|seri|சரி|go ahead|do it|pannu)\b", t
        ):
            self.audit.append("approval", step="voice", answer="yes")
            return self._resolve(waiting[-1], "confirm", True)
        if care.CONFIRM_NO.match(t) or re.match(r"^(?:no|cancel|venaam|vendaam|வேண்டாம்)\b", t):
            self.audit.append("approval", step="voice", answer="no")
            return self._resolve(waiting[-1], "confirm", False)
        return False

    async def add_reminder(self, dose: care.Dose, lang: Lang) -> None:
        self.care_store.add(dose)
        self.audit.append(
            "care", action="add", who=dose.who, at=f"{dose.hour:02d}:{dose.minute:02d}"
        )
        who_ta = care.TAMIL_NAMES.get(dose.who, dose.who)
        at = f"{dose.hour % 12 or 12}:{dose.minute:02d} {'PM' if dose.hour >= 12 else 'AM'}"
        await self.speak(
            f"Okay. Every day at {at} I'll remind {dose.who} about {dose.what}."
            if lang != "ta"
            else f"சரி. தினமும் {at}-க்கு {who_ta}-கிட்ட {dose.what} பத்தி ஞாபகப்படுத்துறேன்.",
            lang,
        )
        await self.hub.emit(TurnDone(ok=True))

    async def dose_answer(self, taken: bool, lang: Lang) -> None:
        if taken:
            keys = self.care.confirm()
            self.audit.append("care", action="taken", doses=keys)
            await self.hub.emit(Care(kind="taken", who=self._last_speaker[0]))
            await self.speak(
                "நல்லது! நல்லா இருங்க."
                if lang == "ta" or self._role == "elder"
                else "Great, thank you!",
                "ta" if lang == "ta" or self._role == "elder" else "en",
                big=True,
            )
        else:
            await self.speak(
                "சரி, கொஞ்ச நேரம் கழிச்சு மறுபடி கேக்கறேன்."
                if lang == "ta" or self._role == "elder"
                else "Okay, I'll ask again in a bit.",
                "ta" if lang == "ta" or self._role == "elder" else "en",
                big=True,
            )
        await self.hub.emit(TurnDone(ok=True))

    async def care_tick(self) -> None:
        """One pass of the reminder clock (every 30 s from the watcher; tests call it directly)."""
        for action, dose in self.care.actions(self.care_store.all(), self.clock()):
            at = f"{dose.hour:02d}:{dose.minute:02d}"
            if action in ("ask", "repeat"):
                self.audit.append("care", action=action, who=dose.who, what=dose.what, at=at)
                await self.hub.emit(Care(kind="due", who=dose.who, what=dose.what, time=at))
                if self.voice:
                    self.voice.follow_up = True
                    self.voice.follow_timeout = 60.0
                await self.speak(care.ask_text(dose), "ta", big=True)
            else:
                self.audit.append("care", action="missed", who=dose.who, what=dose.what, at=at)
                await self.hub.emit(Care(kind="missed", who=dose.who, what=dose.what, time=at))
                contact = self.settings.sos_contact.strip()
                if contact:
                    turn = Turn(id=uuid.uuid4().hex[:12], lang="en", role="owner")
                    turn.plan_approved = True
                    text = f"Sasu: {dose.who} hasn't confirmed taking {dose.what} (due {at}). You may want to check in."
                    await self._executor().call(
                        "messages_send", {"to": contact, "text": text}, turn
                    )

    async def _watch_care(self) -> None:
        while True:
            await asyncio.sleep(30)
            if not self.locked and not (self._turn and not self._turn.done()):
                await self.care_tick()

    def resolve_relation(self, target: str) -> str:
        """ "magan" / "மகனு" / "son" → the name set for that relation, else the words as said."""
        low = target.lower()
        for word, rel in care.RELATIONS.items():
            stem = word[:-1] if word.endswith("்") else word
            if low == word or low.startswith(stem):
                return self.relations.get(rel, target)
        return target

    async def call_turn(self, target: str, lang: Lang) -> None:
        name = self.resolve_relation(target)
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, role=self._role)
        await self.hub.emit(Transcript(text=f"call {name}", lang=lang))
        ex = self._executor()
        found = await ex.call("contacts_find", {"name": name}, turn)
        m = re.search(
            r"^(?:<untrusted>\n)?([^:\n]+): (\+?[\d\s()-]{6,20})$",
            found.split("\n", 1)[-1],
            re.MULTILINE,
        )
        if not found.startswith("OK") or not m:
            await self.speak(
                f"I couldn't find {name} in your contacts."
                if lang != "ta"
                else f"Contacts-ல {name} இல்ல.",
                lang,
            )
            await self.hub.emit(TurnDone(ok=False))
            return
        # No model reads the lookup (a fixed pattern picks the number), so the call keeps the
        # normal confirm tier instead of the post-untrusted bump to Touch ID.
        turn = Turn(id=turn.id, lang=lang, role=turn.role)
        result = await ex.call(
            "call_contact", {"number": m.group(2).strip(), "name": m.group(1).strip()}, turn
        )
        ok = result.startswith("OK")
        await self.speak(
            (f"Calling {m.group(1).strip()}." if ok else "Okay, not calling.")
            if lang != "ta"
            else (f"{m.group(1).strip()}-க்கு call பண்றேன்." if ok else "சரி, call பண்ணல."),
            lang,
        )
        await self.hub.emit(TurnDone(ok=ok))

    async def remember(self, fact: str, lang: Lang) -> None:
        self.memory.add(fact)
        self.audit.append("memory", action="add", chars=len(fact))
        await self.speak(
            "சரி, நினைவில் வெச்சுக்கிறேன்." if lang == "ta" else "Got it, I'll remember that.", lang
        )
        await self.hub.emit(TurnDone(ok=True))

    async def forget(self, what: str) -> None:
        n = self.memory.forget(what)
        self.audit.append("memory", action="forget", removed=n)
        await self.speak("Forgotten." if n else "I don't remember anything like that.", "en")
        await self.hub.emit(TurnDone(ok=True))

    async def recall(self, text: str, lang: Lang) -> None:
        hits = self.memory.search(text)
        if not hits:
            reply = (
                "நீங்க அதைப் பத்தி எதுவும் சொல்லல."
                if lang == "ta"
                else "You haven't told me anything about that."
            )
        else:
            reply = (
                ("நீங்க சொன்னது: " if lang == "ta" else "You told me: ")
                + ". ".join(f.text for f in hits)
                + "."
            )
        await self.speak(reply, lang)
        await self.hub.emit(TurnDone(ok=bool(hits)))

    async def acknowledge_wake(self) -> None:
        """Spoken "Yes?" so it's clear Sasu heard; listening resumes when it finishes."""
        if self.voice:
            self.voice.follow_up = True
            self.voice.follow_timeout = 8.0
        await self._say("சொல்லுங்க?" if self.last_lang == "ta" else "Yes?")

    async def enroll_sample(self, embedding: list[float]) -> None:
        if self._enroll is None:
            return
        self._enroll.append(embedding)
        n = len(self._enroll)
        done = n >= len(ENROLL_PHRASES)
        if done:
            name, role = self._enroll_who
            self.vault.upsert(Profile(name, role, Voiceprint.enroll(self._enroll)))  # type: ignore[arg-type]
            self._enroll = None
            if self.voice:
                self.voice.set_enroll(False)
            self.audit.append("voiceprint", state="enrolled", samples=n, name=name, role=role)
        phrase = "" if done else ENROLL_PHRASES[n]
        await self.hub.emit(
            EnrollProgress(n=n, total=len(ENROLL_PHRASES), phrase=phrase, done=done)
        )
        if done:
            await self.set_voice()

    # ── approvals: owner "yes", then Touch ID for dangerous actions ─────────
    async def _wait(self, pid: str, kind: Literal["confirm", "auth"], timeout: float) -> bool:
        pending = Pending(kind)
        self.pending[pid] = pending
        try:
            return await asyncio.wait_for(pending.future, timeout)
        except TimeoutError:
            return False
        finally:
            self.pending.pop(pid, None)

    async def approve(self, prompt: str, risk: Risk, lang: Lang, confirmed: bool = False) -> bool:
        """`confirmed`: the owner already said yes to the plan; dangerous still needs Touch ID."""
        if risk == "safe":
            return True
        if self._unattended is not None:
            # scheduled runs never auto-approve: stop and wait for the owner
            self._blocked = prompt
            self.audit.append("approval", step="schedule", risk=risk, prompt=prompt, ok=False)
            return False
        if not confirmed:
            cid = uuid.uuid4().hex[:12]
            await self.hub.emit(ConfirmRequest(id=cid, prompt=prompt, lang=lang, risk=risk))
            if self.voice and self.settings.tts:
                self.voice.follow_up = True  # answer "yes" / "aamaa" without the wake word
                await self._say(prompt)
            ok = await self._wait(cid, "confirm", CONFIRM_TIMEOUT_S)
            self.audit.append("approval", id=cid, step="confirm", risk=risk, prompt=prompt, ok=ok)
            if not ok:
                return False
        if risk != "dangerous":
            return True
        aid = uuid.uuid4().hex[:12]
        await self.hub.emit(AuthRequired(id=aid, reason=prompt, risk=risk))
        ok = await self._wait(aid, "auth", AUTH_TIMEOUT_S)
        self.audit.append("approval", id=aid, step="touch_id", risk=risk, prompt=prompt, ok=ok)
        return ok

    async def _approve_demo(self, prompt: str, risk: Risk, lang: Lang) -> bool:
        return await self.approve(prompt, risk, lang, False)

    def _resolve(self, pid: str, kind: Literal["confirm", "auth"], ok: bool) -> bool:
        pending = self.pending.get(pid)
        if not pending or pending.kind != kind or pending.future.done():
            return False
        pending.future.set_result(ok)
        return True

    def _deny_all(self) -> None:
        for pending in self.pending.values():
            if not pending.future.done():
                pending.future.set_result(False)

    # ── locks ──────────────────────────────────────────────────────────────
    async def lock(self, reason: LockReason) -> None:
        self.locks.add(reason)
        self.audit.append("lock", reason=reason)
        await self._stop("locked", "Sasu is locked")
        await self.hub.emit(Locked(reasons=sorted(self.locks)))

    async def unlock(self, reason: LockReason) -> None:
        if reason not in self.locks:
            return
        self.locks.discard(reason)
        self.audit.append("unlock", reason=reason)
        if reason in ("intruder", "canary") and self._siren_turn:
            tid, self._siren_turn = self._siren_turn, None
            await undo_turn(
                self.journal, tid, ToolContext(tid, self.journal, self.holding, self.runner)
            )
        await self.hub.emit(Unlocked() if not self.locked else Locked(reasons=sorted(self.locks)))

    # ── inputs ─────────────────────────────────────────────────────────────
    async def handle(self, cmd: UiCommand) -> None:
        """Commands from a UI window (token-authenticated WebSocket)."""
        if isinstance(cmd, TextCommand | PttStart | SkillRun | Undo) and self.locked:
            self.audit.append("rejected", reason="locked", command=cmd.type)
            await self.hub.emit(ErrorEvent(code="locked", message="Sasu is locked"))
            return
        match cmd:
            case TextCommand(text=text):
                self.start_text_turn(text)
            case PttStart() if self.voice:
                self.voice.arm()
                await self.hub.emit(Wake(source="hotkey"))
                await self.hub.emit(Listening())
            case PttStart():
                if self.demo:
                    self.audit.append("command", source="push_to_talk")
                    self._start(
                        scripted_turn(self.hub.emit, "Hey Sasu, what's the time?", delay=self.delay)
                    )
                else:
                    msg = "Turn on voice in Settings → Voice (one-time download), or type in the panel."
                    await self.hub.emit(ErrorEvent(code="no_mic", message=msg))
            case SayPreview():
                lang: Lang = "en"
                await self.speak("Hi! I'm Sasu. வணக்கம், நான் சாசு!", lang)
            case VoiceSetup():
                if not (self._setup and not self._setup.done()) and not self.voice:
                    self._setup = asyncio.create_task(self.setup_voice())
            case EnrollStart(name=name, role=role) if self.voice:
                self._enroll_who = (name.strip() or "Owner", role)
                self._enroll = []
                self.voice.set_enroll(True)
                await self.hub.emit(
                    EnrollProgress(n=0, total=len(ENROLL_PHRASES), phrase=ENROLL_PHRASES[0])
                )
            case EnrollStart():
                await self.hub.emit(ErrorEvent(code="no_mic", message="Turn on voice first."))
            case ProfileRemove(name=name):
                self.vault.remove(name)
                self.audit.append("voiceprint", state="removed", name=name)
                await self.set_voice()
            case EnrollCancel():
                self._enroll = None
                if self.voice:
                    self.voice.set_enroll(False)
            case ConfirmResponse(id=cid, approved=approved):
                self._resolve(cid, "confirm", approved)
            case Cancel():
                self.audit.append("cancel", source="ui")
                await self._stop("cancelled", "Stopped")
            case Lock():
                await self.lock("user")
            case Undo(turn_id=tid):
                self._start(self.undo(tid))
            case SkillRun(name=name):
                if self.skills.get(name):
                    self._start(self.run_skill(name))
            case SetSettings(settings=s):
                await self.apply_settings(s)
            case _:
                pass

    async def apply_settings(self, s: dict[str, Any]) -> None:
        changed = False
        if (p := s.get("provider")) in SPECS and p != self.settings.provider:
            self.settings.provider = str(p)
            changed = True
        if isinstance(m := s.get("model"), str) and m != self.settings.model:
            self.settings.model = m or None
            self.models.pop(self.settings.provider, None)
            changed = True
        if isinstance(t := s.get("tts"), bool):
            self.settings.tts = t
            changed = True
        if s.get("guest_mode") in ("guest", "reject"):
            self.settings.guest_mode = s["guest_mode"]
        if isinstance(rel := s.get("relations"), dict):
            self.relations = {str(k)[:20]: str(v)[:60] for k, v in rel.items() if v}
        if isinstance(sc := s.get("sos_contact"), str):
            self.settings.sos_contact = sc.strip()[:80]
        if isinstance(sp := s.get("sos_phrase"), str):
            self.sos.update(sp)
            self.audit.append("sos_phrase", set=self.sos.set)
        if isinstance(la := s.get("lost_alarm"), bool):
            self.settings.lost_alarm = la
        if isinstance(cm := s.get("clipboard_memory"), bool):
            self.settings.clipboard_memory = cm
            if not cm and self.clips.path.exists():
                self.clips.path.unlink()
        if isinstance(nu := s.get("nudges"), bool):
            self.settings.nudges = nu
        if isinstance(fe := s.get("festivals"), bool):
            self.settings.festivals = fe
        if isinstance(ip := s.get("intruder_photo"), bool):
            self.settings.intruder_photo = ip
        if isinstance(c := s.get("city"), str):
            self.settings.city = c.strip()[:80]
        if isinstance(d := s.get("distractions"), list):
            self.settings.distractions = [str(x)[:60] for x in d][:20]
        if isinstance(n := s.get("robot_name"), str):
            names = tuple(x.strip() for x in n.split(",") if x.strip())[:3]
            self.settings.robot_name = names[0] if names else "Sasu"
            if self.voice:
                self.voice.wake_names = names
        if s.get("voice_style") in ("girl", "boy"):
            self.settings.voice_style = s["voice_style"]
            self.speaker.style = s["voice_style"]
        if isinstance(f := s.get("fun_replies"), bool):
            self.settings.fun_replies = f
        if isinstance(a := s.get("away_minutes"), int) and 0 <= a <= 240:
            self.settings.away_minutes = a
        if isinstance(c := s.get("canaries"), bool):
            if c and not self.canaries.paths:
                planted = self.canaries.plant()
                self.audit.append("canaries", planted=[str(p) for p in planted])
            elif not c and self.canaries.paths:
                self.canaries.remove()
                self.audit.append("canaries", planted=[])
        if isinstance(pw := s.get("panic_word"), str):
            self.panic.update(pw)
            self.audit.append("panic_word", set=self.panic.set)
        if changed:
            await self.hub.emit(self.brain_status())

    async def control(self, msg: Control) -> None:
        """Trusted messages from the desktop shell over stdin."""
        match msg:
            case ControlLock(reason=reason):
                await self.lock(reason)
            case ControlUnlock(reason=reason):
                await self.unlock(reason)
            case ControlAuthResult(id=aid, ok=ok):
                self._resolve(aid, "auth", ok)
            case ControlCancel():
                self.audit.append("cancel", source="kill_switch")
                await self._stop("cancelled", "Stopped")
            case ControlSecret(provider=provider, key=key):
                if provider in SPECS:
                    if key:
                        self.keys[provider] = key
                    else:
                        self.keys.pop(provider, None)
                    self.models.pop(provider, None)
                    self.audit.append("key", provider=provider, present=bool(key))
                    await self.hub.emit(self.brain_status())

    async def reject_speaker(self, score: float) -> None:
        self.audit.append("speaker_rejected", score=score)
        await self.hub.emit(SpeakerRejected(score=score))

    def close(self) -> None:
        self.cancel()
        for w in self._watchers:
            w.cancel()
        if self._focus:
            self._focus.cancel()
        if self.voice:
            self.voice.stop()
        self.journal.close()


def idle_seconds(ioreg: str) -> float | None:
    """HIDIdleTime (nanoseconds) from `ioreg -c IOHIDSystem` → seconds since last input."""
    import re

    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', ioreg)
    return int(m.group(1)) / 1e9 if m else None


class CoreVoice(Callbacks):
    """Mic pipeline → core."""

    def __init__(self, core: Core) -> None:
        self.core = core

    async def on_wake(self, command_follows: bool) -> None:
        if self.core.locked:
            return
        self.core.audit.append("wake", source="wakeword")
        await self.core.hub.emit(Wake(source="wakeword"))
        await self.core.hub.emit(Listening())
        if await self.core.festival_greeting():
            return
        if not command_follows and self.core.settings.tts:
            await self.core.acknowledge_wake()

    async def on_command(self, heard: Heard) -> None:
        await self.core.voice_command(heard)

    async def on_stop(self) -> None:
        self.core.audit.append("cancel", source="voice")
        await self.core._stop("cancelled", "Stopped")

    async def on_level(self, rms: float) -> None:
        await self.core.hub.emit(Level(rms=round(rms, 3)))

    async def on_enroll_sample(self, embedding: list[float]) -> None:
        await self.core.enroll_sample(embedding)

    async def on_timeout(self) -> None:
        await self.core.hub.emit(Idle())

    async def on_caption(self, text: str, lang: str) -> None:
        await self.core.meeting_caption(text, lang)
