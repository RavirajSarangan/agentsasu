"""Scripted turns so the UI and security flow can be built before voice and brain exist.

Nothing here touches the system: "deleting" files only emits events.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable

from .protocol import (
    ConfirmRequest,
    CoreEvent,
    ErrorEvent,
    Lang,
    Listening,
    Risk,
    SayChunk,
    SayEnd,
    SayStart,
    Sleep,
    SpeakerRejected,
    Thinking,
    ToolEnd,
    ToolStart,
    Transcript,
    TurnDone,
    Wake,
)

Emit = Callable[[CoreEvent], Awaitable[None]]
Approve = Callable[[str, Risk, Lang], Awaitable[bool]]

DANGEROUS = re.compile(r"\b(empty|trash|rm|format|erase)\b|காலி", re.IGNORECASE)
RISKY = re.compile(r"\b(delete|remove|move|send)\b|அழி|நீக்கு", re.IGNORECASE)
STRANGER = re.compile(r"\bstranger\b", re.IGNORECASE)


def detect_lang(text: str) -> Lang:
    return "ta" if any("஀" <= ch <= "௿" for ch in text) else "en"


def _id() -> str:
    return uuid.uuid4().hex[:8]


async def say(emit: Emit, text: str, lang: Lang, *, delay: float = 1.0) -> None:
    """Stream a reply word by word, the way real TTS will."""
    first, *rest = text.split(" ")
    await emit(SayStart(text=first, lang=lang))
    for word in rest:
        await asyncio.sleep(delay * 0.12)
        await emit(SayChunk(text=" " + word))
    await asyncio.sleep(delay * 0.6)
    await emit(SayEnd())


async def _tool(emit: Emit, name: str, summary: str, *, delay: float, risk: Risk = "safe") -> None:
    tid = _id()
    await emit(ToolStart(id=tid, name=name, args={}, risk=risk))
    await asyncio.sleep(delay)
    await emit(ToolEnd(id=tid, ok=True, summary=summary))


async def scripted_turn(
    emit: Emit, text: str, *, delay: float = 1.0, approve: Approve | None = None
) -> None:
    """One fake turn. Risky wording walks through the real approval flow."""
    lang = detect_lang(text)
    await emit(Wake(source="demo"))
    await emit(Listening())
    await asyncio.sleep(delay)

    if STRANGER.search(text):
        await emit(SpeakerRejected(score=0.31))
        await emit(ErrorEvent(code="not_owner", message="Sorry, I only listen to my owner."))
        await emit(TurnDone(ok=False))
        return

    await emit(Transcript(text=text, lang=lang))
    await emit(Thinking())
    await asyncio.sleep(delay)

    risk: Risk | None = (
        "dangerous" if DANGEROUS.search(text) else "confirm" if RISKY.search(text) else None
    )
    if risk and approve:
        await _tool(emit, "files.find", "12 old screenshots", delay=delay)
        prompt = (
            "Move 12 screenshots to the Trash?"
            if risk == "confirm"
            else "Empty the Trash for good?"
        )
        if lang == "ta":
            prompt = (
                "12 screenshots-ஐ Trash-க்கு அனுப்பவா?"
                if risk == "confirm"
                else "Trash-ஐ முழுசா காலி பண்ணவா?"
            )
        if not await approve(prompt, risk, lang):
            await emit(ErrorEvent(code="denied", message="Cancelled — nothing was touched."))
            await emit(TurnDone(ok=False))
            return
        await _tool(emit, "files.trash", "Done (demo: no files touched)", delay=delay, risk=risk)
        await say(
            emit,
            "Done. Your Desktop is clean now."
            if lang == "en"
            else "முடிஞ்சது! Desktop இப்போ சுத்தமா இருக்கு.",
            lang,
            delay=delay,
        )
        await emit(TurnDone(ok=True))
        return

    await _tool(emit, "web_search", "3 results", delay=delay)
    await _tool(emit, "apps.open", "Safari opened", delay=delay)
    reply = (
        "சரி, முடிஞ்சது! Safari இப்போ திறந்திருக்கு."
        if lang == "ta"
        else "Done! Safari is open and ready for you."
    )
    await say(emit, reply, lang, delay=delay)
    await emit(TurnDone(ok=True))


async def demo_loop(emit: Emit, *, delay: float = 1.0, paused: Callable[[], bool]) -> None:
    """Cycle every agent situation forever, covering all robot states. Skips while locked."""
    scenes: list[Callable[[], Awaitable[None]]] = [
        lambda: scripted_turn(emit, "Hey Sasu, open Safari", delay=delay),
        lambda: scripted_turn(emit, "Downloads la irukura PDF ellam list pannu", delay=delay),
        lambda: _confirm_scene(emit, delay),
        lambda: scripted_turn(emit, "stranger says: open my mail", delay=delay),
    ]
    while True:
        for scene in scenes:
            while paused():
                await asyncio.sleep(0.5)
            await scene()
            await asyncio.sleep(delay * 3)
        await emit(Sleep())
        await asyncio.sleep(delay * 6)


async def _confirm_scene(emit: Emit, delay: float) -> None:
    await emit(Wake(source="demo"))
    await emit(Transcript(text="Delete old screenshots", lang="en"))
    await emit(Thinking())
    await asyncio.sleep(delay)
    await emit(
        ConfirmRequest(
            id=_id(), prompt="Delete 12 screenshots from Desktop?", lang="en", risk="confirm"
        )
    )
    await asyncio.sleep(delay * 3)
    await emit(ErrorEvent(code="denied", message="Cancelled — nothing deleted"))
    await emit(TurnDone(ok=False))
