"""The agent loop: model ↔ tools, with every call checked, approved, journaled and audited."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..protocol import CoreEvent, FocusApp, Lang, PlanPreview, Risk, ToolEnd, ToolStart
from ..security.audit import AuditLog
from ..security.policy import Decision, bump, strictest
from ..security.redact import redact_obj
from ..tools import GUEST_TOOLS, REGISTRY, ToolContext, ToolResult, schemas
from ..tools.runtime import Runner, run
from ..undo import Journal
from .prompts import system_prompt, untrusted
from .providers import ChatClient

MAX_STEPS = 12
Emit = Callable[[CoreEvent], Awaitable[None]]
Approve = Callable[[str, Risk, Lang, bool], Awaitable[bool]]


@dataclass
class Turn:
    id: str
    lang: Lang
    guest: bool = False
    untrusted_seen: bool = False
    plan_approved: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)
    sent_chars: int = 0


def confirm_text(name: str, args: dict[str, Any]) -> str:
    """A short human question for an approval prompt."""
    n = len(args.get("paths") or [])
    match name:
        case "files_move":
            return f"Move {n} item(s) to {Path(str(args.get('destination', ''))).name or 'that folder'}?"
        case "files_trash":
            return f"Throw away {n} item(s)? (You can say “Sasu undo”.)"
        case "files_rename":
            return f"Rename {Path(str(args.get('path', ''))).name} to {args.get('new_name')}?"
        case "files_new_folder":
            return f"Create the folder {Path(str(args.get('path', ''))).name}?"
        case "apps_quit":
            return f"Quit {args.get('app')}?"
        case "system_wifi":
            return f"Turn Wi-Fi {'on' if args.get('on') else 'off'}?"
        case "shell_run":
            return f"Run this command: {str(args.get('command', ''))[:160]}"
        case _:
            tool = REGISTRY.get(name)
            return f"Allow {tool.describe_call(args) if tool else name}?"


def _risk(d: Decision) -> Risk:
    return "safe" if d == "deny" else d


class Executor:
    """Runs one tool call under policy, approval, journal and audit. Shared by agent and skills."""

    def __init__(
        self,
        emit: Emit,
        approve: Approve,
        audit: AuditLog,
        journal: Journal,
        holding: Path,
        runner: Runner = run,
    ) -> None:
        self.emit, self.approve, self.audit, self.journal = emit, approve, audit, journal
        self.holding, self.runner = holding, runner

    def decision(self, name: str, args: dict[str, Any], turn: Turn) -> Decision:
        tool = REGISTRY.get(name)
        if tool is None or (turn.guest and name not in GUEST_TOOLS):
            return "deny"
        d = tool.decision(args)
        return bump(d) if turn.untrusted_seen and d != "safe" else d

    async def call(self, name: str, args: dict[str, Any], turn: Turn) -> str:
        tool = REGISTRY.get(name)
        cid = uuid.uuid4().hex[:8]
        d = self.decision(name, args, turn)
        if tool is None or d == "deny":
            why = "guest" if turn.guest else "policy"
            self.audit.append("rejected", reason=why, tool=name, args=args)
            await self.emit(ToolStart(id=cid, name=name, args=args, risk="dangerous"))
            await self.emit(ToolEnd(id=cid, ok=False, summary="Blocked for safety"))
            return "BLOCKED: this action is not allowed. Tell the user briefly."

        if d != "safe":
            covered = turn.plan_approved and d == "confirm"
            if not covered and not await self.approve(
                confirm_text(name, args), d, turn.lang, turn.plan_approved
            ):
                self.audit.append(
                    "tool", tool=name, args=args, decision=d, ok=False, summary="declined"
                )
                return "The user said no. Don't do it; acknowledge briefly."

        await self.emit(ToolStart(id=cid, name=name, args=args, risk=_risk(d)))
        ctx = ToolContext(turn.id, self.journal, self.holding, self.runner)
        try:
            res = await tool.fn(args, ctx)
        except Exception as e:  # a broken tool must not crash the turn
            res = ToolResult(False, f"Failed: {e.__class__.__name__}")
        await self.emit(ToolEnd(id=cid, ok=res.ok, summary=res.summary[:120]))
        if res.app:
            await self.emit(FocusApp(app=res.app))
        self.audit.append("tool", tool=name, args=args, decision=d, ok=res.ok, summary=res.summary)
        turn.calls.append({"tool": name, "args": args})

        content = res.content
        if tool.untrusted_output and content:
            turn.untrusted_seen = True
            content = untrusted(content)
        return f"{'OK' if res.ok else 'FAILED'}: {res.summary}\n{content}".strip()


def needs_plan(calls: list[tuple[str, dict[str, Any]]], ex: Executor, turn: Turn) -> bool:
    decisions = [ex.decision(n, a, turn) for n, a in calls]
    return len(calls) > 1 and any(d in ("confirm", "dangerous") for d in decisions)


class Agent:
    def __init__(self, client: ChatClient, executor: Executor, emit: Emit) -> None:
        self.client, self.ex, self.emit = client, executor, emit

    async def run(self, text: str, turn: Turn, history: list[dict[str, Any]]) -> str:
        """Returns the final reply text (to be spoken)."""
        allowed = GUEST_TOOLS if turn.guest else None
        tools = schemas(allowed)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            *history,
            {"role": "user", "content": text},
        ]
        for step in range(MAX_STEPS):
            outgoing = redact_obj(messages)
            turn.sent_chars += len(json.dumps(outgoing, ensure_ascii=False)) + len(
                json.dumps(tools)
            )
            msg = await self.client.complete(outgoing, tools)
            raw_calls = msg.get("tool_calls") or []
            if not raw_calls:
                return str(msg.get("content") or "").strip() or "Done."

            calls = [
                (c["function"]["name"], _args(c["function"].get("arguments"))) for c in raw_calls
            ]
            if step == 0 and needs_plan(calls, self.ex, turn):
                pid = uuid.uuid4().hex[:8]
                steps = [confirm_text(n, a).rstrip("?") for n, a in calls]
                await self.emit(PlanPreview(id=pid, steps=steps))
                worst: Risk = _risk(strictest(*(self.ex.decision(n, a, turn) for n, a in calls)))
                if not await self.ex.approve(
                    f"Do these {len(calls)} things?", worst, turn.lang, False
                ):
                    return "சரி, எதுவும் செய்யல." if turn.lang == "ta" else "Okay, I won't do that."
                turn.plan_approved = True

            messages.append(
                {"role": "assistant", "content": msg.get("content") or "", "tool_calls": raw_calls}
            )
            for raw, (name, args) in zip(raw_calls, calls, strict=True):
                result = await self.ex.call(name, args, turn)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": raw.get("id", name),
                        "name": name,
                        "content": result,
                    }
                )
        return "That took too many steps, so I stopped. Try a simpler request?"


def _args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
