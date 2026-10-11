from __future__ import annotations

from typing import Any

from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

DESKTOP = applescript('tell application "Finder" to get bounds of window of desktop')
GET = applescript(
    'tell application "System Events" to tell process (item 1 of argv) to get {position, size} of front window'
)
SET = applescript(
    'tell application "System Events" to tell process (item 1 of argv)',
    "set position of front window to {(item 2 of argv) as integer, (item 3 of argv) as integer}",
    "set size of front window to {(item 4 of argv) as integer, (item 5 of argv) as integer}",
    "end tell",
)
MENU_BAR = 25


def _nums(out: str) -> list[int]:
    return [int(float(x)) for x in out.replace("{", "").replace("}", "").split(",") if x.strip()]


def frames(layout: str, n: int, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """(x, y, width, height) for each of n windows on a w×h screen."""
    top, height = MENU_BAR, h - MENU_BAR
    if layout == "full" or n == 1:
        return [(0, top, w, height)] * n
    if layout == "stack":
        part = height // n
        return [(0, top + i * part, w, part) for i in range(n)]
    part = w // n  # side by side ("split", "thirds")
    return [(i * part, top, part, height) for i in range(n)]


async def _set(ctx: ToolContext, app: str, x: int, y: int, w: int, h: int) -> bool:
    return (await ctx.run([*SET, app, str(x), str(y), str(w), str(h)])).ok


@tool(
    "windows_arrange",
    "Arrange the front windows of up to 3 apps: side by side, stacked, or full screen. Undoable.",
    obj(
        ["apps"],
        apps={"type": "array", "items": {"type": "string"}, "maxItems": 3},
        layout={"type": "string", "enum": ["split", "stack", "full"]},
    ),
)
async def windows_arrange(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    apps = [str(a).strip() for a in args["apps"] if str(a).strip()][:3]
    layout = str(args.get("layout") or "split")
    if not apps:
        return ToolResult(False, "Which apps?")
    b = _nums((await ctx.run(DESKTOP)).out)
    w, h = (b[2], b[3]) if len(b) == 4 else (1440, 900)
    done = 0
    for app, (x, y, fw, fh) in zip(apps, frames(layout, len(apps), w, h), strict=True):
        await ctx.run(["open", "-a", app])
        prev = _nums((await ctx.run([*GET, app])).out)
        if await _set(ctx, app, x, y, fw, fh):
            done += 1
            if len(prev) == 4:
                ctx.journal.record(ctx.turn_id, "window", app=app, prev=prev)
    if not done:
        return ToolResult(False, "Couldn't move the windows (allow Accessibility for Sasu)")
    return ToolResult(True, f"Arranged {' and '.join(apps)}", app=apps[0])


@inverse("window", lambda d: f"moved {d['app']}'s window")
async def _undo_window(d: dict[str, Any], ctx: ToolContext) -> None:
    x, y, w, h = d["prev"]
    await _set(ctx, d["app"], x, y, w, h)
