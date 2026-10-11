"""What each kind of person may ask Sasu to do.

owner   everything (dangerous steps still need Touch ID)
family  everything except dangerous steps and raw shell commands
elder   same as family (Amma mode adds slow Tamil speech, big text, care features)
kid     music, volume, time, jokes, and only kid-friendly websites
guest   the tiny guest set (an unknown voice)
"""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from ..tools.registry import GUEST_TOOLS
from .policy import Decision

Role = Literal["owner", "family", "elder", "kid", "guest"]

KID_TOOLS = {
    "media_control",
    "media_now_playing",
    "system_volume",
    "system_volume_step",
    "system_info",
    "web_open",
}
KID_SITES = {
    "youtube.com",
    "www.youtube.com",
    "youtubekids.com",
    "www.youtubekids.com",
    "m.youtube.com",
}
FAMILY_DENY = {"shell_run"}


def allowed(role: Role, tool: str, args: dict[str, Any], decision: Decision) -> Decision:
    """The decision after applying the speaker's role (never looser than `decision`)."""
    if role == "owner" or decision == "deny":
        return decision
    if role in ("family", "elder"):
        if tool in FAMILY_DENY or decision == "dangerous":
            return "deny"
        return decision
    if role == "kid":
        if tool not in KID_TOOLS:
            return "deny"
        if tool == "web_open":
            url = str(args.get("url", ""))
            host = urlparse(url if "://" in url else "https://" + url).hostname or ""
            if host not in KID_SITES:
                return "deny"
        return decision
    return decision if tool in GUEST_TOOLS else "deny"
