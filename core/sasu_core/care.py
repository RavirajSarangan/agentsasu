"""Amma mode: Sasu looks after elderly family members.

- Medicine reminders: "Amma-ku 8 mani BP maathirai reminder vai", "remind appa to take sugar
  tablet at 9 pm", "அம்மாவுக்கு 8 மணிக்கு BP மாத்திரை நினைவூட்டு". Sasu asks slowly in
  Tamil at the time, listens for "ஆமா / aamaa / yes", repeats once after 15 minutes, and
  alerts the owner if the dose is still not confirmed.
- Calling family by voice ("magan-ku call pannu") and a "help / உதவி" alert.
The schedule is encrypted with the vault key; nothing leaves the Mac except alert texts.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD = b"sasu-care-v1"
REPEAT_AFTER_S = 15 * 60
MISSED_AFTER_S = 30 * 60

WHO = {
    "amma": "amma", "ammaa": "amma", "mom": "amma", "mum": "amma", "mother": "amma", "அம்மா": "amma",
    "appa": "appa", "dad": "appa", "father": "appa", "அப்பா": "appa",
    "paati": "paati", "patti": "paati", "grandma": "paati", "பாட்டி": "paati",
    "thatha": "thatha", "thaatha": "thatha", "grandpa": "thatha", "தாத்தா": "thatha",
}  # fmt: skip
TAMIL_NAMES = {"amma": "அம்மா", "appa": "அப்பா", "paati": "பாட்டி", "thatha": "தாத்தா"}
_WHO = "|".join(sorted(map(re.escape, WHO), key=len, reverse=True))

_AM = r"(?:am|a\.m\.|morning|kaalai|kalai|காலை)"
_PM = r"(?:pm|p\.m\.|evening|night|raathiri|rathiri|iravu|saayangaalam|மாலை|இரவு|ராத்திரி)"

REMIND = [
    # remind amma to take BP tablet at 8 pm
    re.compile(
        rf"remind\s+(?P<who>{_WHO})\s+to\s+take\s+(?:(?:her|his|the)\s+)?(?P<what>.+?)\s+at\s+(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}}))?\s*(?P<ap>{_AM}|{_PM})?\s*$",
        re.IGNORECASE,
    ),
    # amma-ku 8 mani BP maathirai reminder vai / amma ku raathiri 8 mani ...
    re.compile(
        rf"(?P<who>{_WHO})\s*-?\s*(?:ku|kku|ukku|வுக்கு|க்கு)?\s+(?:(?P<ap1>{_AM}|{_PM})\s+)?(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}}))?\s*(?:mani|மணி(?:க்கு)?)\s+(?P<what>.+?)\s+(?:reminder\s+(?:vai|vei|podu)|ரிமைண்டர்\s*வை|நினைவூட்டு)\s*$",
        re.IGNORECASE,
    ),
]
CONFIRM_YES = re.compile(
    r"^(?:yes|yeah|yep|done|taken|i took it|aamaa|aama|amaa|saapten|sapten|saapitten|potten|ஆமா|ஆமாம்|சாப்பிட்டேன்|போட்டேன்)\b",
    re.IGNORECASE,
)
CONFIRM_NO = re.compile(r"^(?:no|not yet|illa|illai|innum illa|இல்ல|இன்னும் இல்ல)\b", re.IGNORECASE)
HELP = re.compile(
    r"\b(?:help|help me|udhavi|udavi|kaapathunga|kapathunga)\b|உதவி|காப்பாத்துங்க", re.IGNORECASE
)
CALL = re.compile(
    r"^(?:hey\s+)?(?:\w+[,\s]+)?(?:call|phone|ring)\s+(?P<a>.+?)$"
    r"|^(?P<b>.+?)\s*-?\s*(?:ku|kku|ukku)?\s+(?:call|phone|kaal|fone)\s+(?:pannu|panu|pannunga|podu)$"
    r"|^(?P<c>.+?)(?:க்கு|உக்கு|வுக்கு)?\s+(?:போன்|கால்)\s+(?:பண்ணு|பண்ணுங்க)$",
    re.IGNORECASE,
)
RELATIONS = {
    "magan": "son", "son": "son", "மகன்": "son", "magal": "daughter", "daughter": "daughter", "மகள்": "daughter",
    "amma": "mother", "mom": "mother", "அம்மா": "mother", "appa": "father", "dad": "father", "அப்பா": "father",
}  # fmt: skip


@dataclass
class Dose:
    id: str
    who: str  # amma | appa | paati | thatha | a name
    what: str
    hour: int
    minute: int


def _hour(h: int, ap: str | None) -> int | None:
    if not 0 <= h <= 23:
        return None
    if ap:
        pm = re.fullmatch(_PM, ap, re.IGNORECASE) is not None
        if h > 12:
            return h
        return (h % 12) + (12 if pm else 0)
    # No am/pm: 1–6 means afternoon/evening (nobody takes tablets at 3 am by default).
    return h + 12 if 1 <= h <= 6 else h


def parse_reminder(text: str) -> Dose | None:
    t = re.sub(r"^(?:hey\s+)?(?:sasu[,\s]+)?", "", text.strip().rstrip(".!"), flags=re.IGNORECASE)
    for pat in REMIND:
        m = pat.search(t)
        if not m:
            continue
        g = m.groupdict()
        hour = _hour(int(g["h"]), g.get("ap") or g.get("ap1"))
        minute = int(g.get("m") or 0)
        if hour is None or minute > 59:
            return None
        who = WHO.get(g["who"].lower(), g["who"].lower())
        return Dose(uuid.uuid4().hex[:8], who, g["what"].strip(), hour, minute)
    return None


def call_target(text: str) -> str | None:
    m = CALL.search(text.strip().rstrip(".!"))
    if not m:
        return None
    raw = (m.group("a") or m.group("b") or m.group("c") or "").strip()
    raw = re.sub(r"\s*-?\s*(?:ku|kku|ukku)$", "", raw, flags=re.IGNORECASE)
    return raw or None


def ask_text(d: Dose) -> str:
    who = TAMIL_NAMES.get(d.who, d.who)
    return f"{who}, {d.what} நேரம். சாப்பிட்டீங்களா?"


class CareStore:
    def __init__(self, path: Path, aead: AESGCM) -> None:
        self.path = path
        self._aead = aead

    def all(self) -> list[Dose]:
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        return [Dose(**d) for d in json.loads(self._aead.decrypt(raw[:12], raw[12:], AAD))]

    def _save(self, doses: list[Dose]) -> None:
        nonce = os.urandom(12)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(
            nonce + self._aead.encrypt(nonce, json.dumps([asdict(d) for d in doses]).encode(), AAD)
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def add(self, d: Dose) -> Dose:
        self._save([*self.all(), d][-50:])
        return d

    def remove(self, did: str) -> bool:
        doses = self.all()
        keep = [d for d in doses if d.id != did]
        self._save(keep)
        return len(keep) != len(doses)


@dataclass
class DoseState:
    asked_at: float
    repeats: int = 0
    taken: bool = False
    missed: bool = False


class Tracker:
    """Which doses are due, asked, repeated, taken or missed today. `now` is injectable."""

    def __init__(self) -> None:
        self.state: dict[str, DoseState] = {}

    @staticmethod
    def key(d: Dose, day: str) -> str:
        return f"{day}:{d.id}"

    def actions(self, doses: list[Dose], now: float) -> list[tuple[str, Dose]]:
        """[("ask" | "repeat" | "missed", dose)] that should happen at `now`."""
        lt = time.localtime(now)
        day = time.strftime("%Y-%m-%d", lt)
        minutes_now = lt.tm_hour * 60 + lt.tm_min
        out: list[tuple[str, Dose]] = []
        for d in doses:
            k = self.key(d, day)
            st = self.state.get(k)
            due = minutes_now >= d.hour * 60 + d.minute
            if st is None:
                # Only ask within an hour of the time (don't nag at midnight about breakfast).
                if due and minutes_now - (d.hour * 60 + d.minute) <= 60:
                    self.state[k] = DoseState(asked_at=now)
                    out.append(("ask", d))
                continue
            if st.taken or st.missed:
                continue
            if st.repeats == 0 and now - st.asked_at >= REPEAT_AFTER_S:
                st.repeats = 1
                out.append(("repeat", d))
            elif st.repeats >= 1 and now - st.asked_at >= MISSED_AFTER_S:
                st.missed = True
                out.append(("missed", d))
        return out

    def pending(self) -> list[str]:
        return [k for k, s in self.state.items() if not s.taken and not s.missed]

    def confirm(self) -> list[str]:
        done = self.pending()
        for k in done:
            self.state[k].taken = True
        return done

    def status(self, d: Dose, now: float) -> str:
        st = self.state.get(self.key(d, time.strftime("%Y-%m-%d", time.localtime(now))))
        if st is None:
            return "upcoming"
        return "taken" if st.taken else "missed" if st.missed else "asked"
