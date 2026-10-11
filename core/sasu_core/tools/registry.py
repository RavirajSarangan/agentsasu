"""Tool registry: every capability Sasu has, with its risk floor and policy check."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..security.policy import Decision
from ..undo import Journal
from .runtime import Proc, Runner, run


@dataclass
class ToolResult:
    ok: bool
    summary: str
    content: str = ""
    app: str | None = None


@dataclass
class ToolContext:
    turn_id: str
    journal: Journal
    holding: Path
    runner: Runner = run
    home: Path = field(default_factory=Path.home)

    async def run(
        self, args: Sequence[str], timeout: float = 15.0, stdin: str | None = None
    ) -> Proc:
        return await self.runner(args, timeout, stdin)


ToolFn = Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
DecideFn = Callable[[dict[str, Any]], Decision]


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, Any]
    risk: Decision
    fn: ToolFn
    decide: DecideFn | None = None
    untrusted_output: bool = False
    guest_ok: bool = False

    def decision(self, args: dict[str, Any]) -> Decision:
        from ..security.policy import strictest

        return strictest(self.risk, self.decide(args)) if self.decide else self.risk

    def describe_call(self, args: dict[str, Any]) -> str:
        shown = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)[:60]}" for k, v in args.items())
        return f"{self.name}({shown})"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.params,
            },
        }


REGISTRY: dict[str, Tool] = {}


def obj(required: list[str] | None = None, **props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or []}


def tool(
    name: str,
    description: str,
    params: dict[str, Any],
    *,
    risk: Decision = "safe",
    decide: DecideFn | None = None,
    untrusted_output: bool = False,
    guest_ok: bool = False,
) -> Callable[[ToolFn], ToolFn]:
    def wrap(fn: ToolFn) -> ToolFn:
        REGISTRY[name] = Tool(
            name, description, params, risk, fn, decide, untrusted_output, guest_ok
        )
        return fn

    return wrap


def schemas(allowed: set[str] | None = None) -> list[dict[str, Any]]:
    return [t.schema() for t in REGISTRY.values() if allowed is None or t.name in allowed]


GUEST_TOOLS = {"system_info", "media_control", "media_now_playing"}
