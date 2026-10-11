from __future__ import annotations

from typing import Any

from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool


@tool("clipboard_get", "Read the clipboard text.", obj(), untrusted_output=True)
async def clipboard_get(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    p = await ctx.run(["pbpaste"])
    return ToolResult(p.ok, "Read clipboard", p.out[:5000])


@tool(
    "clipboard_set", "Copy text to the clipboard. Undoable.", obj(["text"], text={"type": "string"})
)
async def clipboard_set(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    prev = (await ctx.run(["pbpaste"])).out
    await ctx.run(["pbcopy"], 5, str(args["text"]))
    ctx.journal.record(ctx.turn_id, "clipboard", prev=prev[:20_000])
    return ToolResult(True, "Copied")


@inverse("clipboard", lambda d: "copied text")
async def _undo_clip(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(["pbcopy"], 5, d["prev"])
