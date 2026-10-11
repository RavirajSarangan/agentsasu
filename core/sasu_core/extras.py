"""Small unique extras: voice-typing, read-aloud, festival greetings, proactive nudges."""

from __future__ import annotations

import datetime as dt
import re

TYPE = re.compile(
    r"^(?:hey\s+)?(?:\w+[,\s]+)?(?:type\s+(?:this|pannu|panu)?[:,\s]+|type pannu[:,\s]+|டைப்\s*பண்ணு[:,\s]+)(?P<text>.+)$",
    re.IGNORECASE,
)
READ = re.compile(
    r"^(?:hey\s+)?(?:\w+[,\s]+)?(?:read\s+(?:this|it|that|the selection|the clipboard)(?:\s+to me|\s+out)?|padichu\s+sollu|padi|படிச்சு\s*சொல்லு|படி)[.!?]?$",
    re.IGNORECASE,
)

# Fixed-date festivals; lunar ones listed per year (local table, works offline).
FESTIVALS: dict[str, tuple[str, str, str]] = {
    "01-14": ("pongal", "Happy Pongal!", "இனிய பொங்கல் நல்வாழ்த்துகள்!"),
    "04-14": ("puthandu", "Happy Tamil New Year!", "இனிய தமிழ் புத்தாண்டு நல்வாழ்த்துகள்!"),
    "12-25": ("christmas", "Merry Christmas!", "இனிய கிறிஸ்துமஸ் நல்வாழ்த்துகள்!"),
    "01-01": ("newyear", "Happy New Year!", "இனிய புத்தாண்டு நல்வாழ்த்துகள்!"),
}
DEEPAVALI = {2026: "11-08", 2027: "10-29", 2028: "10-17"}


def festival(today: dt.date | None = None) -> tuple[str, str, str] | None:
    """(id, English greeting, Tamil greeting) if today is a festival."""
    d = today or dt.date.today()
    key = d.strftime("%m-%d")
    if DEEPAVALI.get(d.year) == key:
        return ("deepavali", "Happy Deepavali!", "இனிய தீபாவளி நல்வாழ்த்துகள்!")
    return FESTIVALS.get(key)


def parse_type(text: str) -> str | None:
    m = TYPE.match(text.strip())
    return m.group("text").strip() if m else None


def is_read(text: str) -> bool:
    return bool(READ.match(text.strip()))
