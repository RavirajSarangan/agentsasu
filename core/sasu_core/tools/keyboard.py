from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ..security.policy import path_decision
from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

PASTE = applescript('tell application "System Events" to keystroke "v" using command down')
COPY = applescript('tell application "System Events" to keystroke "c" using command down')
FRONT = applescript(
    'tell application "System Events" to return name of first process whose frontmost is true'
)


@tool(
    "type_text",
    "Type text (English or Tamil) into the app in front, at the cursor.",
    obj(["text"], text={"type": "string"}),
    risk="confirm",
)
async def type_text(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    text = str(args["text"])[:5000]
    app = (await ctx.run(FRONT)).out.strip()
    prev = (await ctx.run(["pbpaste"])).out
    await ctx.run(["pbcopy"], 5, text)
    p = await ctx.run(PASTE)
    await asyncio.sleep(0.25)
    await ctx.run(["pbcopy"], 5, prev)  # the clipboard is put back right away
    if not p.ok:
        return ToolResult(False, "Couldn't type (allow Accessibility for Sasu)")
    return ToolResult(
        True, f"Typed {len(text)} characters into {app or 'the front app'}", app=app or None
    )


async def selected_text(ctx: ToolContext) -> str:
    """Selected text in the front app (via ⌘C), leaving the clipboard as it was."""
    prev = (await ctx.run(["pbpaste"])).out
    await ctx.run(["pbcopy"], 5, "")
    await ctx.run(COPY)
    await asyncio.sleep(0.25)
    sel = (await ctx.run(["pbpaste"])).out
    await ctx.run(["pbcopy"], 5, prev)
    return sel.strip() or prev.strip()


@tool(
    "files_reveal",
    "Show a file in Finder (select it).",
    obj(["path"], path={"type": "string"}),
    decide=lambda a: path_decision(str(a.get("path", "~")), write=False),
)
async def files_reveal(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = Path(str(args["path"])).expanduser().resolve()
    if not path.exists():
        return ToolResult(False, "No such file")
    p = await ctx.run(["open", "-R", str(path)])
    return ToolResult(p.ok, f"Showing {path.name}", app="Finder")
