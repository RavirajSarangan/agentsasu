"""“Focus 25 minutes”: close distractions, quiet the Mac, then put everything back.

Focus runs as one undoable turn. When the timer ends (or on "stop focus") the turn is
undone, so the apps reopen and the volume returns.
"""

from __future__ import annotations

import re

DEFAULT_DISTRACTIONS = ["Messages", "WhatsApp", "Slack", "Discord", "Telegram"]

_UNIT = r"(?:min(?:ute)?s?|nimisham|நிமிடம்)"
START = re.compile(
    rf"\bfocus(?:\s+mode)?(?:\s+(?:for\s+)?(\d{{1,3}})\s*{_UNIT})?\b|(\d{{1,3}})\s*{_UNIT}\s*focus|கவனம்",
    re.IGNORECASE,
)
STOP = re.compile(
    r"\b(?:stop|end|cancel)\s+focus\b|focus\s+(?:mudinjathu|podhum|pothum|stop)|கவனம்\s*போதும்",
    re.IGNORECASE,
)


def parse_start(text: str) -> int | None:
    """Minutes to focus, or None if this isn't a focus request."""
    t = text.strip()
    if len(t.split()) > 8 or STOP.search(t):
        return None
    m = START.search(t)
    if not m:
        return None
    return max(1, min(int(m.group(1) or m.group(2) or 25), 180))


def is_stop(text: str) -> bool:
    return bool(STOP.search(text))
