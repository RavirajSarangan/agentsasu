"""Things the owner asks Sasu to remember. AES-256-GCM on disk, same key as the voiceprint.

"remember amma's birthday is June 3" → saved
"when is amma's birthday?" / "amma birthday enna sonnen?" → recalled
"forget amma's birthday" → deleted
Only the owner can save or read memories; they never reach guest or kid turns.
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

AAD = b"sasu-memory-v1"

SAVE = re.compile(
    r"^(?:hey\s+)?(?:\w+[,\s]+)?(?:please\s+)?(?:remember|note)\s+(?:that\s+)?(?P<fact>.{3,300})$"
    r"|^(?P<fact2>.{3,300}?)\s*(?:-?nu\s+)?(?:nyabagam|nyaabagam|gnabagam)\s+(?:vechukko|vachukko|vechiko)$"
    r"|^(?P<fact3>.{3,300}?)\s*(?:என்று\s*)?நினைவில்\s*வை$",
    re.IGNORECASE,
)
FORGET = re.compile(
    r"^(?:hey\s+)?(?:\w+[,\s]+)?forget\s+(?:about\s+)?(?P<what>.{2,120})$|(?P<what2>.{2,120}?)\s+marandhudu$",
    re.IGNORECASE,
)
RECALL = re.compile(
    r"\bwhat did i (?:tell|ask) you (?:about|to remember)\b|\bdo you remember\b|\bwhat do you remember\b"
    r"|enna sonnen|nyabagam irukka|நினைவு இருக்கா|என்ன சொன்னேன்",
    re.IGNORECASE,
)
STOP = {"the", "a", "an", "is", "my", "me", "of", "to", "on", "in", "and", "what", "when", "where", "did", "i", "you",
        "about", "tell", "remember", "enna", "sonnen", "do", "that", "it", "for", "s"}  # fmt: skip


@dataclass
class Fact:
    id: str
    text: str
    at: float


def _words(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+|[஀-௿]+", text.lower()) if w not in STOP and len(w) > 1
    }


class Memory:
    def __init__(self, path: Path, aead: AESGCM) -> None:
        self.path = path
        self._aead = aead

    def all(self) -> list[Fact]:
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        return [Fact(**f) for f in json.loads(self._aead.decrypt(raw[:12], raw[12:], AAD))]

    def _save(self, facts: list[Fact]) -> None:
        nonce = os.urandom(12)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(
            nonce + self._aead.encrypt(nonce, json.dumps([asdict(f) for f in facts]).encode(), AAD)
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def add(self, text: str) -> Fact:
        fact = Fact(uuid.uuid4().hex[:10], text.strip().rstrip("."), time.time())
        self._save([*self.all(), fact][-500:])
        return fact

    def search(self, query: str, limit: int = 3) -> list[Fact]:
        q = _words(query)
        scored = [(len(q & _words(f.text)), f) for f in self.all()]
        return [f for s, f in sorted(scored, key=lambda x: (-x[0], -x[1].at)) if s > 0][:limit]

    def forget(self, what: str) -> int:
        """Delete facts matching `what` (by id or by best keyword overlap). Returns how many."""
        facts = self.all()
        keep = [f for f in facts if f.id != what.strip()]
        if len(keep) == len(facts):
            hits = {f.id for f in self.search(what, limit=1)}
            keep = [f for f in facts if f.id not in hits]
        self._save(keep)
        return len(facts) - len(keep)


def parse_save(text: str) -> str | None:
    m = SAVE.match(text.strip().rstrip(".!"))
    if not m:
        return None
    return (m.group("fact") or m.group("fact2") or m.group("fact3") or "").strip() or None


def parse_forget(text: str) -> str | None:
    m = FORGET.match(text.strip().rstrip(".!"))
    return (m.group("what") or m.group("what2")).strip() if m else None
