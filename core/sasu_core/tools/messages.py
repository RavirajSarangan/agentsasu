from __future__ import annotations

import re
from typing import Any

from .registry import ToolContext, ToolResult, obj, tool
from .runtime import applescript

SEND = applescript(
    'tell application "Messages"',
    "set svc to 1st account whose service type = iMessage",
    "send (item 1 of argv) to participant (item 2 of argv) of svc",
    "end tell",
)
CONTACT = re.compile(r"^(?:\+?[\d\s()-]{6,20}|[^@\s]+@[^@\s]+\.[a-z]{2,})$", re.IGNORECASE)


@tool(
    "messages_send",
    "Send an iMessage/SMS to a phone number or email. Only use when the user explicitly asks.",
    obj(["to", "text"], to={"type": "string"}, text={"type": "string"}),
    risk="confirm",
)
async def messages_send(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    to = str(args["to"]).strip()
    text = str(args["text"])[:1000]
    if not CONTACT.match(to):
        return ToolResult(False, "That doesn't look like a phone number or email")
    p = await ctx.run([*SEND, text, to])
    return ToolResult(
        p.ok,
        "Message sent" if p.ok else "Messages couldn't send it (allow Automation for Sasu)",
        app="Messages",
    )
