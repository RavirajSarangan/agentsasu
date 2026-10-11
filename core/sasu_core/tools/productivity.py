from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript


@tool(
    "reminders_add",
    "Add a reminder to Apple Reminders. Undoable.",
    obj(["title"], title={"type": "string"}),
)
async def reminders_add(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    title = str(args["title"]).strip()[:200]
    p = await ctx.run(
        [
            *applescript(
                'tell application "Reminders" to return id of (make new reminder with properties {name:(item 1 of argv)})'
            ),
            title,
        ]
    )
    if not p.ok:
        return ToolResult(False, "Reminders didn't respond (allow Automation for Sasu)")
    ctx.journal.record(ctx.turn_id, "reminder", id=p.out.strip(), title=title)
    return ToolResult(True, f"Reminder: {title}", app="Reminders")


@inverse("reminder", lambda d: f"added reminder “{d['title']}”")
async def _undo_reminder(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(
        [
            *applescript(
                'tell application "Reminders" to delete (first reminder whose id is (item 1 of argv))'
            ),
            d["id"],
        ]
    )


@tool(
    "notes_add",
    "Create a note in Apple Notes. Undoable.",
    obj(["title", "body"], title={"type": "string"}, body={"type": "string"}),
)
async def notes_add(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    title = str(args["title"]).strip()[:200]
    body = str(args["body"])[:10_000]
    p = await ctx.run(
        [
            *applescript(
                'tell application "Notes" to return id of (make new note with properties {name:(item 1 of argv), body:(item 2 of argv)})'
            ),
            title,
            body,
        ]
    )
    if not p.ok:
        return ToolResult(False, "Notes didn't respond (allow Automation for Sasu)")
    ctx.journal.record(ctx.turn_id, "note", id=p.out.strip(), title=title)
    return ToolResult(True, f"Note: {title}", app="Notes")


@inverse("note", lambda d: f"created note “{d['title']}”")
async def _undo_note(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(
        [*applescript('tell application "Notes" to delete note id (item 1 of argv)'), d["id"]]
    )


@tool("screen_capture", "Take a screenshot and save it to the Desktop. Undoable.", obj())
async def screen_capture(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = ctx.home / "Desktop" / f"Sasu Screenshot {time.strftime('%Y-%m-%d at %H.%M.%S')}.png"
    p = await ctx.run(["screencapture", "-x", str(path)])
    if not p.ok or not path.exists():
        return ToolResult(False, "Screenshot failed (allow Screen Recording for Sasu)")
    ctx.journal.record(ctx.turn_id, "created_file", path=str(path))
    return ToolResult(True, f"Saved {path.name}")


@inverse("created_file", lambda d: f"created {Path(d['path']).name}")
async def _undo_created(d: dict[str, Any], ctx: ToolContext) -> None:
    import shutil

    src = Path(d["path"])
    if src.exists():
        dst = ctx.holding / "undone" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
