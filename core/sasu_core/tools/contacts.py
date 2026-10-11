from __future__ import annotations

import re
from typing import Any

from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

FIND = applescript(
    "set out to {}",
    'tell application "Contacts"',
    "repeat with p in (every person whose name contains (item 1 of argv))",
    "repeat with ph in phones of p",
    'set end of out to (name of p) & ": " & (value of ph)',
    "end repeat",
    "end repeat",
    "end tell",
    "set AppleScript's text item delimiters to linefeed",
    "return out as text",
)
NUMBER = re.compile(r"^\+?[\d\s()-]{6,20}$")


@tool(
    "contacts_find",
    "Look up phone numbers in the Mac's Contacts by name.",
    obj(["name"], name={"type": "string"}),
    untrusted_output=True,
)
async def contacts_find(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    name = str(args["name"]).strip()[:60]
    if not name:
        return ToolResult(False, "Who should I look for?")
    p = await ctx.run([*FIND, name])
    lines = [line for line in p.out.splitlines() if line.strip()][:10]
    if not p.ok:
        return ToolResult(False, "Contacts didn't respond (allow Contacts for Sasu)")
    return ToolResult(True, f"{len(lines)} number(s) for {name}", "\n".join(lines))


@tool(
    "call_contact",
    "Start a FaceTime audio call to a phone number. Asks first.",
    obj(["number"], number={"type": "string"}, name={"type": "string"}),
    risk="confirm",
)
async def call_contact(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    number = str(args["number"]).strip()
    if not NUMBER.match(number):
        return ToolResult(False, "That doesn't look like a phone number")
    digits = re.sub(r"[^\d+]", "", number)
    p = await ctx.run(["open", f"facetime-audio://{digits}"])
    who = str(args.get("name") or number)
    return ToolResult(p.ok, f"Calling {who}" if p.ok else "FaceTime didn't start", app="FaceTime")
