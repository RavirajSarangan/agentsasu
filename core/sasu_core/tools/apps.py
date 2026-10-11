from __future__ import annotations

from typing import Any

from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

APP = {
    "type": "string",
    "description": "Application name, e.g. Safari, Spotify, Visual Studio Code",
}


async def is_running(ctx: ToolContext, app: str) -> bool:
    p = await ctx.run([*applescript("return application (item 1 of argv) is running"), app])
    return p.out.strip() == "true"


@tool("apps_open", "Open (or switch to) a Mac application.", obj(["app"], app=APP))
async def apps_open(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    app = str(args["app"]).strip()
    was_running = await is_running(ctx, app)
    p = await ctx.run(["open", "-a", app])
    if not p.ok:
        return ToolResult(False, f"Couldn't find an app called {app}")
    ctx.journal.record(ctx.turn_id, "app_open", app=app, was_running=was_running)
    return ToolResult(True, f"{app} opened", app=app)


@inverse("app_open", lambda d: f"opened {d['app']}")
async def _undo_open(d: dict[str, Any], ctx: ToolContext) -> None:
    if not d.get("was_running"):
        await ctx.run([*applescript("tell application (item 1 of argv) to quit"), d["app"]])


@tool("apps_quit", "Quit a running Mac application.", obj(["app"], app=APP), risk="confirm")
async def apps_quit(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    app = str(args["app"]).strip()
    p = await ctx.run([*applescript("tell application (item 1 of argv) to quit"), app])
    if not p.ok:
        return ToolResult(False, f"Couldn't quit {app}")
    ctx.journal.record(ctx.turn_id, "app_quit", app=app)
    return ToolResult(True, f"{app} quit")


@inverse("app_quit", lambda d: f"quit {d['app']}")
async def _undo_quit(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(["open", "-a", d["app"]])


@tool("apps_list", "List the apps that are open right now.", obj(), guest_ok=False)
async def apps_list(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    p = await ctx.run(
        applescript(
            'tell application "System Events" to get name of every process whose background only is false'
        )
    )
    names = [n.strip() for n in p.out.split(",") if n.strip()]
    return ToolResult(p.ok, f"{len(names)} apps open", ", ".join(names))
