from __future__ import annotations

from typing import Any

from ..security.policy import Decision, shell_decision
from .registry import ToolContext, ToolResult, obj, tool


def _decide(args: dict[str, Any]) -> Decision:
    return shell_decision(str(args.get("command", "")))


@tool(
    "shell_run",
    "Run a terminal command. Prefer the specific tools; use this only when nothing else fits. Not undoable.",
    obj(["command"], command={"type": "string"}, minutes={"type": "number"}),
    risk="confirm",
    decide=_decide,
    untrusted_output=True,
)
async def shell_run(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    cmd = str(args["command"])
    # long jobs (tests, builds) may ask for up to an hour; the default stays 30 s
    limit = min(3600.0, max(30.0, float(args.get("minutes") or 0) * 60))
    p = await ctx.run(["/bin/zsh", "-c", cmd], limit, None)
    out = (p.out + ("\n" + p.err if p.err else ""))[:6000]
    return ToolResult(p.ok, f"exit {p.code}", out)
