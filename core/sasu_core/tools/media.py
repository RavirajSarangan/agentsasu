from __future__ import annotations

from typing import Any

from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

PLAYERS = {"Music", "Spotify"}
ACTIONS = {
    "play": "play",
    "pause": "pause",
    "playpause": "playpause",
    "next": "next track",
    "previous": "previous track",
}


@tool(
    "media_control",
    "Play, pause or skip music in Apple Music or Spotify.",
    obj(
        ["action"],
        action={"type": "string", "enum": list(ACTIONS)},
        player={
            "type": "string",
            "enum": sorted(PLAYERS),
            "description": "Default: Spotify if it's open, else Music",
        },
    ),
    guest_ok=True,
)
async def media_control(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    action = ACTIONS.get(str(args["action"]))
    player = str(args.get("player") or "Spotify")
    if action is None or player not in PLAYERS:
        return ToolResult(False, "Unknown player or action")
    # Fixed script per allow-listed player: app terms must be known at compile time.
    p = await ctx.run(applescript(f'tell application "{player}" to {action}'))
    return ToolResult(
        p.ok, f"{player}: {args['action']}" if p.ok else f"{player} didn't respond", app=player
    )


@tool("media_now_playing", "What song is playing in Spotify or Music.", obj(), guest_ok=True)
async def media_now_playing(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    for player in ("Spotify", "Music"):
        p = await ctx.run(
            applescript(
                f'if application "{player}" is running then tell application "{player}" to return (name of current track) & " — " & (artist of current track)'
            )
        )
        if p.ok and p.out.strip():
            return ToolResult(True, p.out.strip(), f"{player}: {p.out.strip()}")
    return ToolResult(True, "Nothing playing")
