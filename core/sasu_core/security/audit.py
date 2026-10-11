"""Append-only, hash-chained audit log.

Every row stores sha256(prev_hash | at | kind | data). Editing, deleting or reordering
any row breaks the chain, which `verify()` reports. SQLite triggers also refuse
UPDATE and DELETE so the app itself can't rewrite history by accident.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .redact import redact_obj

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  at    REAL NOT NULL,
  kind  TEXT NOT NULL,
  data  TEXT NOT NULL,
  prev  TEXT NOT NULL,
  hash  TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
  BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
  BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


def _digest(prev: str, at: float, kind: str, data: str) -> str:
    return hashlib.sha256(f"{prev}|{at:.6f}|{kind}|{data}".encode()).hexdigest()


@dataclass(frozen=True)
class Entry:
    id: int
    at: float
    kind: str
    data: dict[str, Any]
    hash: str


@dataclass(frozen=True)
class ChainStatus:
    ok: bool
    entries: int
    broken_at: int | None = None


class AuditLog:
    def __init__(self, path: Path | str) -> None:
        path = Path(path)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.executescript(SCHEMA)
        os.chmod(path, 0o600)  # owner-only: other local users can't read history
        self._lock = threading.Lock()

    def append(self, kind: str, **data: Any) -> Entry:
        body = json.dumps(redact_obj(data), sort_keys=True, ensure_ascii=False, default=str)
        with self._lock:
            row = self._db.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            at = time.time()
            digest = _digest(prev, at, kind, body)
            cur = self._db.execute(
                "INSERT INTO audit (at, kind, data, prev, hash) VALUES (?, ?, ?, ?, ?)",
                (at, kind, body, prev, digest),
            )
        return Entry(cur.lastrowid or 0, at, kind, json.loads(body), digest)

    def recent(self, limit: int = 100) -> list[Entry]:
        rows = self._db.execute(
            "SELECT id, at, kind, data, hash FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Entry(r[0], r[1], r[2], json.loads(r[3]), r[4]) for r in rows]

    def since(self, ts: float) -> list[Entry]:
        rows = self._db.execute(
            "SELECT id, at, kind, data, hash FROM audit WHERE at >= ? ORDER BY id", (ts,)
        ).fetchall()
        return [Entry(r[0], r[1], r[2], json.loads(r[3]), r[4]) for r in rows]

    def verify(self) -> ChainStatus:
        prev = GENESIS
        count = 0
        for rid, at, kind, data, stored_prev, stored in self._db.execute(
            "SELECT id, at, kind, data, prev, hash FROM audit ORDER BY id"
        ):
            count += 1
            if stored_prev != prev or _digest(prev, at, kind, data) != stored:
                return ChainStatus(ok=False, entries=count, broken_at=rid)
            prev = stored
        return ChainStatus(ok=True, entries=count)

    def close(self) -> None:
        self._db.close()
