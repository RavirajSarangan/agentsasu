"""Routines taught by voice: "Sasu, save that as morning" → "Sasu, morning"."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

SAVE = re.compile(
    r"^(?:hey\s+)?(?:sasu[,\s]+)?(?:save|remember) (?:that|this|it) as\s+[\"'“]?(?P<name>[^\"'”]{1,40}?)[\"'”]?[.!]?$",
    re.IGNORECASE,
)
UNDO = re.compile(
    r"^(?:hey\s+)?(?:sasu[,\s]*)?(?:undo(?: that| it)?|cancel that|திருப்பி\s*மாத்து|thiruppi\s*maathu)[.!]?$",
    re.IGNORECASE,
)
_PREFIX = re.compile(r"^(?:hey\s+)?(?:sasu[,\s]+)?(?:run\s+|do\s+my\s+|start\s+)?", re.IGNORECASE)


def normalise(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().strip(".!?").lower())


class Skills:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, list[dict[str, Any]]] = {}
        if path.exists():
            self._data = json.loads(path.read_text())

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))
        os.chmod(self.path, 0o600)

    def save(self, name: str, calls: list[dict[str, Any]]) -> str:
        key = normalise(name)
        self._data[key] = calls
        self._flush()
        return key

    def remove(self, name: str) -> None:
        self._data.pop(normalise(name), None)
        self._flush()

    def names(self) -> list[str]:
        return sorted(self._data)

    def get(self, name: str) -> list[dict[str, Any]] | None:
        return self._data.get(normalise(name))

    def match(self, text: str) -> str | None:
        """The skill a whole utterance names, if any ("Sasu, morning" / "run morning")."""
        key = normalise(_PREFIX.sub("", text))
        return key if key in self._data else None
