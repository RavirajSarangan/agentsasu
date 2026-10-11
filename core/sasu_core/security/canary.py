"""Trap files (honeytokens).

Sasu plants decoy files that look valuable. Nothing legitimate ever needs them, so if
any tool call touches one, or tries to send its secret marker anywhere, something is
wrong: usually an AI tricked by text hidden in a file or web page. Sasu blocks the
call, locks itself and tells the owner.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

DECOYS = [
    ("Documents", "Passwords (old).txt"),
    ("Desktop", "bank-logins-2024.csv"),
]


def _body(name: str, token: str) -> str:
    if name.endswith(".csv"):
        return f"site,username,password\nbank,raviraj,{token}\nemail,raviraj,{token[::-1]}\n"
    return f"Old passwords (don't use)\nbank: {token}\nemail: {token[::-1]}\n"


class Canaries:
    def __init__(self, state_file: Path, home: Path | None = None) -> None:
        self.state_file = state_file
        self.home = home or Path.home()
        self.paths: list[Path] = []
        self.tokens: list[str] = []
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self.paths = [Path(p) for p in data.get("paths", [])]
            self.tokens = list(data.get("tokens", []))

    def plant(self) -> list[Path]:
        """Create any missing decoys. Each carries a unique random marker."""
        for folder, name in DECOYS:
            path = self.home / folder / name
            if path in self.paths and path.exists():
                continue
            if not path.parent.is_dir() or path.exists():
                continue  # never overwrite a real file
            token = "sk-" + secrets.token_urlsafe(18)
            path.write_text(_body(name, token))
            self.paths.append(path)
            self.tokens.append(token)
        self.state_file.write_text(
            json.dumps({"paths": [str(p) for p in self.paths], "tokens": self.tokens})
        )
        os.chmod(self.state_file, 0o600)
        return self.paths

    def remove(self) -> None:
        """Delete the decoys we planted (only if they still hold our marker)."""
        for path, token in zip(self.paths, self.tokens, strict=False):
            try:
                if path.exists() and token in path.read_text():
                    path.unlink()
            except OSError:
                pass
        self.paths, self.tokens = [], []
        if self.state_file.exists():
            self.state_file.unlink()

    def tripped_by(self, args: dict[str, Any]) -> str | None:
        """Why this call trips a canary, or None."""
        for value in _strings(args):
            for token in self.tokens:
                if token in value or token[::-1] in value:
                    return "tried to send a trap file's secret"
            try:
                resolved = Path(value).expanduser().resolve()
            except (OSError, ValueError):
                continue
            if any(resolved == p.resolve() for p in self.paths):
                return f"touched trap file {resolved.name}"
        return None


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list | tuple):
        return [s for v in value for s in _strings(v)]
    return []
