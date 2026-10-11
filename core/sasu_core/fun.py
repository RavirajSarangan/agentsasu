"""Small delights and helpers that don't need the AI: jokes, the panic word, reports."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import secrets
import time
from pathlib import Path

from .security.audit import AuditLog

JOKE = re.compile(r"\b(joke|jokes|kadi)\b|ஜோக்|நகைச்சுவை", re.IGNORECASE)
REPORT = re.compile(r"\b(security|safety)\s+(report|check|status)\b|பாதுகாப்பு", re.IGNORECASE)

JOKES = {
    "en": [
        "Why did the robot go on holiday? It needed to recharge. Seri, seri, I'll stop.",
        "I asked the Wi-Fi for its password. It said: nothing personal, I just don't connect with everyone.",
        "I tried to delete your Downloads folder once. Then I remembered undo exists. Bayam illa!",
        "What do you call a robot that always takes the long way? R2-Detour.",
    ],
    "ta": [
        "என் Wi-Fi password என்ன தெரியுமா? 'தெரியாது'. அதான் password!",
        "நான் robot-னு சொன்னா நம்ப மாட்டாங்க. ஆனா charge போடாம விட்டா தூங்கிடுவேன். அப்ப நான் யாரு?",
        "Battery 1% இருக்கும்போது தான் நான் ரொம்ப வேகமா வேலை செய்வேன். நம்ம எல்லாரும் அப்படித்தான்!",
    ],
}


def joke(lang: str) -> str:
    return random.choice(JOKES["ta" if lang == "ta" else "en"])


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[஀-௿]+", text.lower())


class PanicWord:
    """A secret phrase that locks Sasu instantly. Only a salted hash is stored."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._salt = ""
        self._hash = ""
        self._len = 0
        if path.exists():
            d = json.loads(path.read_text())
            self._salt, self._hash, self._len = d["salt"], d["hash"], int(d["len"])

    @property
    def set(self) -> bool:
        return bool(self._hash)

    def _h(self, words: list[str]) -> str:
        return hashlib.sha256((self._salt + " ".join(words)).encode()).hexdigest()

    def update(self, phrase: str) -> None:
        words = _words(phrase)
        if not words or len(" ".join(words)) < 3:
            self._salt = self._hash = ""
            self._len = 0
            self.path.unlink(missing_ok=True)
            return
        self._salt = secrets.token_hex(16)
        self._len = len(words)
        self._hash = self._h(words)
        self.path.write_text(json.dumps({"salt": self._salt, "hash": self._hash, "len": self._len}))
        os.chmod(self.path, 0o600)

    def heard_in(self, text: str) -> bool:
        if not self._hash:
            return False
        words = _words(text)
        n = self._len
        return any(self._h(words[i : i + n]) == self._hash for i in range(0, len(words) - n + 1))


def security_report(audit: AuditLog, since: float | None = None) -> str:
    start = since if since is not None else time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    entries = audit.since(start)
    commands = sum(e.kind == "command" for e in entries)
    tools = sum(e.kind == "tool" and e.data.get("ok") is True for e in entries)
    blocked = sum(e.kind in ("rejected",) for e in entries)
    strangers = sum(e.kind in ("speaker_rejected", "guest", "intruder") for e in entries)
    alarms = sum(e.kind == "alarm" for e in entries)
    chain = audit.verify()
    parts = [
        f"Today you gave me {commands} request{'s' if commands != 1 else ''} and I did {tools} action{'s' if tools != 1 else ''}."
    ]
    parts.append(
        f"{strangers} attempt{'s' if strangers != 1 else ''} by other voices."
        if strangers
        else "No one else tried to use me."
    )
    if blocked:
        parts.append(f"I blocked {blocked} request{'s' if blocked != 1 else ''}.")
    if alarms:
        parts.append(
            f"{alarms} security alarm{'s' if alarms != 1 else ''} went off. Check the Security page."
        )
    parts.append("My log is intact." if chain.ok else "Warning: my log has been tampered with.")
    return " ".join(parts)
