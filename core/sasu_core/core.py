"""The running agent: turns, approvals, locks, brain, undo, skills."""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import fastpath
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
    Fun,
    Idle,
    Intruder,
    Lang,
    Level,
    Listening,
    Lock,
    Locked,
    LockReason,
    Privacy,
    PttStart,
    Risk,
    SayChunk,
    SayEnd,
    SayPreview,
    SayStart,
    SetSettings,
    SkillRun,
    SpeakerRejected,
    TextCommand,
    Thinking,
    Transcript,
    TurnDone,
    UiCommand,
    Undo,
    UndoAvailable,
    Undone,
    Unlocked,
    VoiceSetup,
    VoiceStatus,
    Wake,
)
from .security.audit import AuditLog
from .security.canary import Canaries
from .security.voiceprint import Voiceprint, VoiceprintVault
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

    def start_text_turn(self, text: str, *, guest: bool = False, lang: Lang | None = None) -> None:
        text = text.strip()
        if self.panic.heard_in(text):
            self._start(self.panic_lock())
            return
        if not guest and self.intruders_unseen:
            notice = self.intruders_unseen
            self.intruders_unseen = []
            self._start(self._notice_then(notice, text, lang))
            return
        if guest:  # guests get a tiny tool set, nothing else
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

    async def tell_joke(self, lang: Lang) -> None:
        await self.hub.emit(Fun(kind="joke"))
        await self.speak(joke(lang), lang)
        await self.hub.emit(TurnDone(ok=True))

    async def on_alarm(self, kind: str, detail: str) -> None:
        if kind == "canary":
            await self.lock("canary")

    async def fast_turn(
        self, text: str, fast: fastpath.Fast, lang: Lang, *, guest: bool = False
    ) -> None:
        """Common requests, done locally in about a second."""
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, guest=guest)
        self.audit.append(
            "command", source="guest" if guest else "owner", text=text, turn=turn.id, fast=fast.kind
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

    async def speak(self, text: str, lang: Lang) -> None:
        """Streams the caption word by word while the Mac voice speaks it."""
        words = text.split(" ")
        voice = asyncio.create_task(self._say(text)) if self.settings.tts else None
        await self.hub.emit(SayStart(text=words[0], lang=lang))
        for w in words[1:]:
            await asyncio.sleep(0.07 if voice else 0.03)
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
        turn = Turn(id=uuid.uuid4().hex[:12], lang=lang, guest=guest)
        self.audit.append("command", source="guest" if guest else "owner", text=text, turn=turn.id)
        await self.hub.emit(Transcript(text=text, lang=lang))
        await self.hub.emit(Thinking())
        client = await self._client()
        ok = True
        try:
            reply = await Agent(client, self._executor(), self.hub.emit).run(
                text, turn, list(self.history)
            )
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
        ctx = ToolContext(tid, self.journal, self.holding)
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
        self.voice_state = self.voice_state.model_copy(
            update={"enrolled": self.vault.path.exists(), **changes}
        )
        await self.hub.emit(self.voice_state)

    async def boot(self) -> None:
        """Start listening if the voice models are already on disk, and the watchers."""
        self._watchers = [
            asyncio.create_task(self._watch_away()),
            asyncio.create_task(self._watch_music()),
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
        guest = False
        voiceprint = self.vault.load()
        recently_owner = _time.monotonic() - self.owner_verified_at < 60
        if voiceprint is not None:
            verdict = voiceprint.verify(heard.embedding) if heard.embedding else None
            if verdict is not None and verdict.ok:
                self.owner_verified_at = _time.monotonic()
            elif verdict is None and recently_owner:
                pass  # too short to check, but the owner was verified moments ago
            elif verdict is None:
                await self.speak(
                    "Sorry, say that again?" if lang != "ta" else "மறுபடியும் சொல்லுங்க?", lang
                )
                if self.voice:
                    self.voice.arm()
                return
            else:
                score = verdict.score
                self.intruders_unseen.append(heard.text)
                self.audit.append("intruder", text=heard.text, score=score)
                await self.hub.emit(
                    Intruder(text=heard.text, score=score, count=len(self.intruders_unseen))
                )
                if self.settings.guest_mode == "reject":
                    await self.reject_speaker(score)
                    await self.hub.emit(
                        ErrorEvent(code="not_owner", message="Sorry, I only listen to my owner.")
                    )
                    await self.speak("Sorry, I only listen to my owner.", "en")
                    await self.hub.emit(TurnDone(ok=False))
                    return
                self.audit.append("guest", score=score)
                guest = True
        if self.voice:
            self.voice.follow_up = True  # keep listening after the reply, no wake word needed
        self.start_text_turn(heard.text, guest=guest, lang=lang)

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
            self.vault.save(Voiceprint.enroll(self._enroll))
            self._enroll = None
            if self.voice:
                self.voice.set_enroll(False)
            self.audit.append("voiceprint", state="enrolled", samples=n)
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
        if not confirmed:
            cid = uuid.uuid4().hex[:12]
            await self.hub.emit(ConfirmRequest(id=cid, prompt=prompt, lang=lang, risk=risk))
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
            case EnrollStart() if self.voice:
                self._enroll = []
                self.voice.set_enroll(True)
                await self.hub.emit(
                    EnrollProgress(n=0, total=len(ENROLL_PHRASES), phrase=ENROLL_PHRASES[0])
                )
            case EnrollStart():
                await self.hub.emit(ErrorEvent(code="no_mic", message="Turn on voice first."))
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
