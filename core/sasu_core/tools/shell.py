from __future__ import annotations

from typing import Any

from ..security.policy import Decision, shell_decision
from .registry import ToolContext, ToolResult, obj, tool


def _decide(args: dict[str, Any]) -> Decision:
    return shell_decision(str(args.get("command", "")))


@tool(
    "shell_run",
    "Run a terminal command. Prefer the specific tools; use this only when nothing else fits. Not undoable.",
    obj(["command"], command={"type": "string"}),
    risk="confirm",
    decide=_decide,
    untrusted_output=True,
)
async def shell_run(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    cmd = str(args["command"])
    p = await ctx.run(["/bin/zsh", "-c", cmd], 30, None)
    out = (p.out + ("\n" + p.err if p.err else ""))[:6000]
    return ToolResult(p.ok, f"exit {p.code}", out)
