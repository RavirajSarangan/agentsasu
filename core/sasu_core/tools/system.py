from __future__ import annotations

import re
from typing import Any

from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript


async def _volume(ctx: ToolContext) -> int:
    p = await ctx.run(applescript("return output volume of (get volume settings)"))
    try:
        return int(p.out.strip())
    except ValueError:
        return 50


async def _set_volume(ctx: ToolContext, level: int) -> None:
    await ctx.run(
        [*applescript("set volume output volume (item 1 of argv as integer)"), str(level)]
    )


@tool(
    "system_volume",
    "Set the Mac's output volume (0–100).",
    obj(["level"], level={"type": "integer", "minimum": 0, "maximum": 100}),
    guest_ok=True,
)
async def system_volume(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    level = max(0, min(100, int(args["level"])))
    prev = await _volume(ctx)
    await _set_volume(ctx, level)
    ctx.journal.record(ctx.turn_id, "volume", prev=prev, level=level)
    return ToolResult(True, f"Volume {level}")


@tool(
    "system_volume_step",
    "Make the Mac louder or quieter by a step (-100…100).",
    obj(["delta"], delta={"type": "integer", "minimum": -100, "maximum": 100}),
    guest_ok=True,
)
async def system_volume_step(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    prev = await _volume(ctx)
    level = max(0, min(100, prev + int(args["delta"])))
    await _set_volume(ctx, level)
    ctx.journal.record(ctx.turn_id, "volume", prev=prev, level=level)
    return ToolResult(True, f"Volume {level}")


@inverse("volume", lambda d: f"volume {d['prev']} → {d['level']}")
async def _undo_volume(d: dict[str, Any], ctx: ToolContext) -> None:
    await _set_volume(ctx, int(d["prev"]))


async def _dark(ctx: ToolContext) -> bool:
    p = await ctx.run(
        applescript(
            'tell application "System Events" to tell appearance preferences to return dark mode'
        )
    )
    return p.out.strip() == "true"


async def _set_dark(ctx: ToolContext, on: bool) -> None:
    await ctx.run(
        [
            *applescript(
                'tell application "System Events" to tell appearance preferences to set dark mode to (item 1 of argv is "true")'
            ),
            "true" if on else "false",
        ]
    )


@tool("system_dark_mode", "Turn dark mode on or off.", obj(["on"], on={"type": "boolean"}))
async def system_dark_mode(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    on = bool(args["on"])
    prev = await _dark(ctx)
    await _set_dark(ctx, on)
    ctx.journal.record(ctx.turn_id, "dark_mode", prev=prev, on=on)
    return ToolResult(True, f"Dark mode {'on' if on else 'off'}")


@inverse("dark_mode", lambda d: f"dark mode {'on' if d['on'] else 'off'}")
async def _undo_dark(d: dict[str, Any], ctx: ToolContext) -> None:
    await _set_dark(ctx, bool(d["prev"]))


async def _wifi_device(ctx: ToolContext) -> str:
    p = await ctx.run(["networksetup", "-listallhardwareports"])
    m = re.search(r"Hardware Port: Wi-Fi\s*\nDevice: (\w+)", p.out)
    return m.group(1) if m else "en0"


@tool("system_wifi", "Turn Wi-Fi on or off.", obj(["on"], on={"type": "boolean"}), risk="confirm")
async def system_wifi(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    on = bool(args["on"])
    dev = await _wifi_device(ctx)
    prev = "On" in (await ctx.run(["networksetup", "-getairportpower", dev])).out
    p = await ctx.run(["networksetup", "-setairportpower", dev, "on" if on else "off"])
    if not p.ok:
        return ToolResult(False, "Couldn't change Wi-Fi")
    ctx.journal.record(ctx.turn_id, "wifi", prev=prev, on=on, device=dev)
    return ToolResult(True, f"Wi-Fi {'on' if on else 'off'}")


@inverse("wifi", lambda d: f"Wi-Fi {'on' if d['on'] else 'off'}")
async def _undo_wifi(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(["networksetup", "-setairportpower", d["device"], "on" if d["prev"] else "off"])


@tool("system_info", "Current time, date, battery level and macOS version.", obj(), guest_ok=True)
async def system_info(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    date = (await ctx.run(["date", "+%A %d %B %Y, %H:%M"])).out.strip()
    batt = (await ctx.run(["pmset", "-g", "batt"])).out
    m = re.search(r"(\d+)%;\s*([\w ]+);", batt)
    battery = f"{m.group(1)}% ({m.group(2).strip()})" if m else "unknown"
    ver = (await ctx.run(["sw_vers", "-productVersion"])).out.strip()
    return ToolResult(True, "System info", f"Time: {date}\nBattery: {battery}\nmacOS {ver}")
