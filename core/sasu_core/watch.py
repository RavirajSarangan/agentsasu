"""Watch & tell: Sasu keeps an eye on something and speaks up when it happens.

"download mudinja sollu", "100% aana sollu", "indha page-la price kuranja sollu",
"indha file maarina sollu", "run npm test and tell me when it's done".
Each watch is a small poller task; the core owns them (start, list, stop) and announces.
Page text is never shown to the AI: only a price number or a change is compared.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx

Kind = Literal["download", "battery", "page", "file", "command"]
MAX_WATCHES = 10

_TELL = r"(?:sollu|sollunga|tell me|let me know|சொல்லு|சொல்லுங்க)"
DOWNLOAD = re.compile(
    r"download(?:\s+(?:mudinja|mudinjathum|mudinjadhum|finish(?:es|ed)?|is done|completes?))|"
    r"when (?:the |my |this )?download (?:is )?(?:done|finish(?:es|ed)?|completes?)|டவுன்லோட்\s*முடிஞ்ச",
    re.IGNORECASE,
)
BATTERY = re.compile(
    rf"(?:battery\s+)?(?P<n>\d{{1,3}})\s*(?:%|percent)\s*(?:aana|ana|aanadhum|reach(?:es)?|ஆனா)\s*{_TELL}"
    rf"|(?:tell me|let me know) when (?:the )?battery (?:is|reaches|hits|gets to) (?P<m>\d{{1,3}})"
    rf"|(?P<full>full\s*charge|fully charged)\s*(?:aana|ana|aanadhum|ஆனா)?\s*{_TELL}",
    re.IGNORECASE,
)
PAGE = re.compile(
    rf"(?:indha|intha|this|இந்த)\s+(?:page|website|site|பேஜ்)(?:-?la|-?ல|\s+on)?\s+(?P<what>.*?)\s*{_TELL}"
    rf"|(?:tell me|let me know) when (?:the |this )?(?P<what2>price drops|price goes down|page changes)",
    re.IGNORECASE,
)
FILE = re.compile(
    rf"(?:indha|intha|this|இந்த)\s+file\s+(?:maarina|maarinaa|mari(?:na)?|changes?|மாறினா)\s*{_TELL}"
    rf"|(?:tell me|let me know) when (?:this|the selected) file changes",
    re.IGNORECASE,
)
COMMAND = re.compile(
    r"^(?:hey\s+)?(?:sasu[,\s]+)?run\s+[`\"'“]?(?P<a>.+?)[`\"'”]?\s+and\s+(?:tell me|let me know)\s+when\s+(?:it'?s\s+|it is\s+)?(?:done|finished)"
    r"|^[`\"'“]?(?P<b>.+?)[`\"'”]?\s+run\s+pann?i\s+mudinja\s+(?:sollu|sollunga)",
    re.IGNORECASE,
)
STOP = re.compile(
    r"\bstop watching\b|\bwatch(?:ing)?\s+(?:podhum|pothum|stop|venaam)\b|பார்க்கறது\s*போதும்",
    re.IGNORECASE,
)
LIST = re.compile(
    r"\bwhat are you watching\b|\bwatch list\b|\benna (?:ellam )?watch pann", re.IGNORECASE
)

PARTIAL = (".crdownload", ".download", ".part", ".partial")
PRICE = re.compile(r"(?:₹|Rs\.?|INR|£|\$|€)\s?(\d[\d,]*(?:\.\d{1,2})?)")
_TAGS = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.IGNORECASE | re.DOTALL)


@dataclass
class Request:
    kind: Kind
    level: int = 0  # battery
    price: bool = False  # page: price drop (True) or any change
    command: str = ""


def parse(text: str) -> Request | None:
    t = text.strip().rstrip(".!?")
    if m := COMMAND.search(t):
        return Request("command", command=(m.group("a") or m.group("b")).strip("`\"'“” "))
    if DOWNLOAD.search(t):
        return Request("download")
    if m := BATTERY.search(t):
        level = 100 if m.group("full") else int(m.group("n") or m.group("m"))
        return Request("battery", level=max(1, min(100, level)))
    if FILE.search(t):
        return Request("file")
    if m := PAGE.search(t):
        what = (m.group("what") or m.group("what2") or "").lower()
        return Request(
            "page", price=bool(re.search(r"price|vilai|விலை|kuranj|kammi|drop|down", what))
        )
    return None


@dataclass
class Watch:
    kind: Kind
    label: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


# ── checks (pure; the core polls them) ───────────────────────────────────────


def partials(folder: Path) -> set[str]:
    if not folder.is_dir():
        return set()
    return {p.name for p in folder.iterdir() if p.name.endswith(PARTIAL)}


def newest_file(folder: Path) -> Path | None:
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and not p.name.endswith(PARTIAL)
    ]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def battery_percent(pmset: str) -> int | None:
    m = re.search(r"(\d+)%", pmset)
    return int(m.group(1)) if m else None


def page_text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub(" ", html)).strip()


def first_price(text: str) -> float | None:
    m = PRICE.search(text)
    return float(m.group(1).replace(",", "")) if m else None


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def fetch(url: str, transport: httpx.AsyncBaseTransport | None = None) -> str | None:
    if not re.match(r"^https?://", url):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": "Mozilla/5.0 Sasu"},
        ) as c:
            r = await c.get(url)
            return page_text(r.text[:2_000_000]) if r.status_code < 400 else None
    except httpx.HTTPError:
        return None
