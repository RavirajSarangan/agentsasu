"""Scheduled tasks: "Daily 9 mani-ku mail summary pannu", "every Friday 6 pm Downloads clean
pannu", "weekdays 8:30-ku good morning sollu".

A task is just a request Sasu runs at a time, through the normal routing. Runs are
unattended: safe steps happen, but anything that needs a yes is never auto-approved; the run
stops as "needs you" until the owner says "Sasu, run it" or presses Run in the panel.
The list is encrypted with the vault key.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .care import _AM, _PM, _hour

AAD = b"sasu-tasks-v1"
WINDOW_MIN = 60  # a task missed by more than an hour (Mac asleep) waits for its next day
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS = {
    "monday": 0, "mon": 0, "thingal": 0, "திங்கள்": 0,
    "tuesday": 1, "tue": 1, "sevvai": 1, "செவ்வாய்": 1,
    "wednesday": 2, "wed": 2, "budhan": 2, "puthan": 2, "புதன்": 2,
    "thursday": 3, "thu": 3, "vyazhan": 3, "viyazhan": 3, "வியாழன்": 3,
    "friday": 4, "fri": 4, "velli": 4, "வெள்ளி": 4,
    "saturday": 5, "sat": 5, "sani": 5, "சனி": 5,
    "sunday": 6, "sun": 6, "nyayiru": 6, "gnayiru": 6, "ஞாயிறு": 6,
}  # fmt: skip
_DAY = "|".join(sorted(map(re.escape, DAYS), key=len, reverse=True))
_WHEN = (
    r"(?P<daily>daily|every\s*day|everyday|dhinamum|thinamum|தினமும்)"
    r"|(?P<weekdays>weekdays|every\s+weekday|on\s+weekdays)"
    rf"|(?:every|ovvoru|ஒவ்வொரு)\s+(?P<d1>{_DAY})"
    rf"|(?P<d2>{_DAY})\s*-?\s*(?:thorum|torum|தோறும்)"
)
_TIME = (
    rf"(?:at\s+)?(?:(?P<ap1>{_AM}|{_PM})\s+)?(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}}))?\s*"
    rf"(?P<ap>{_AM}|{_PM})?\s*(?:mani|மணி|o'?clock)?(?:\s*-?\s*(?:ku|kku|க்கு))?"
)
_PREFIX = r"^(?:hey\s+)?(?:sasu[,\s]+)?"
FRONT = re.compile(rf"{_PREFIX}(?:{_WHEN})(?:\s+{_TIME})?[,\s]+(?P<req>.+)$", re.IGNORECASE)
BACK = re.compile(rf"{_PREFIX}(?P<req>.+?)[,\s]+(?:{_WHEN})(?:\s+{_TIME})?$", re.IGNORECASE)
RUN_IT = re.compile(
    r"^(?:hey\s+)?(?:sasu[,\s]+)?(?:run it|ok(?:ay)?,? run it|do it now|ippo pannu|seri,? pannu|சரி,? பண்ணு)[.!]?$",
    re.IGNORECASE,
)


@dataclass
class Task:
    request: str
    days: list[int]
    hour: int
    minute: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    enabled: bool = True
    last_day: str = ""
    last_state: str = ""  # done | needs_you | failed
    last_summary: str = ""


def parse(text: str) -> Task | None:
    t = text.strip().rstrip(".!")
    for pat in (FRONT, BACK):
        m = pat.search(t)
        if not m:
            continue
        g = m.groupdict()
        req = re.sub(r"^(?:to|and)\s+", "", g["req"].strip(" ,"), flags=re.IGNORECASE)
        if len(req) < 3:
            return None
        if g["daily"]:
            days = list(range(7))
        elif g["weekdays"]:
            days = list(range(5))
        else:
            days = [DAYS[(g["d1"] or g["d2"]).lower()]]
        hour, minute = 9, 0
        if g["h"]:
            h = _hour(int(g["h"]), g["ap"] or g["ap1"])
            minute = int(g["m"] or 0)
            if h is None or minute > 59:
                return None
            hour = h
        return Task(req, days, hour, minute)
    return None


def clock(t: Task) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'PM' if t.hour >= 12 else 'AM'}"


def when(t: Task) -> str:
    if len(t.days) == 7:
        return f"Every day at {clock(t)}"
    if t.days == list(range(5)):
        return f"Weekdays at {clock(t)}"
    return f"{', '.join(DAY_NAMES[d] + 's' for d in t.days)} at {clock(t)}"


def due(t: Task, now: float) -> bool:
    lt = time.localtime(now)
    since = lt.tm_hour * 60 + lt.tm_min - (t.hour * 60 + t.minute)
    return (
        t.enabled
        and lt.tm_wday in t.days
        and t.last_day != time.strftime("%Y-%m-%d", lt)
        and 0 <= since <= WINDOW_MIN
    )


class TaskStore:
    def __init__(self, path: Path, aead: AESGCM) -> None:
        self.path = path
        self._aead = aead

    def all(self) -> list[Task]:
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        return [Task(**d) for d in json.loads(self._aead.decrypt(raw[:12], raw[12:], AAD))]

    def _save(self, items: list[Task]) -> None:
        nonce = os.urandom(12)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(
            nonce + self._aead.encrypt(nonce, json.dumps([asdict(t) for t in items]).encode(), AAD)
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def add(self, t: Task) -> Task:
        self._save([*self.all(), t][-30:])
        return t

    def get(self, tid: str) -> Task | None:
        return next((t for t in self.all() if t.id == tid), None)

    def update(self, t: Task) -> None:
        self._save([t if x.id == t.id else x for x in self.all()])

    def remove(self, tid: str) -> bool:
        items = self.all()
        keep = [t for t in items if t.id != tid]
        self._save(keep)
        return len(keep) != len(items)
