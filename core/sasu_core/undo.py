""" "Sasu, undo" — every change a tool makes is journaled with how to reverse it.

Tools call `journal.record(turn_id, kind, **data)` after a change and register an
inverse with `@inverse(kind)`. `undo_turn` replays a turn's inverses newest-first.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tools.registry import ToolContext

Inverse = Callable[[dict[str, Any], "ToolContext"], Awaitable[None]]
INVERSES: dict[str, Inverse] = {}
DESCRIBE: dict[str, Callable[[dict[str, Any]], str]] = {}


def inverse(kind: str, describe: Callable[[dict[str, Any]], str]) -> Callable[[Inverse], Inverse]:
    def wrap(fn: Inverse) -> Inverse:
        INVERSES[kind] = fn
        DESCRIBE[kind] = describe
        return fn

    return wrap


@dataclass(frozen=True)
class Action:
    id: int
    turn_id: str
    kind: str
    data: dict[str, Any]

    def describe(self) -> str:
        fn = DESCRIBE.get(self.kind)
        return fn(self.data) if fn else self.kind


class Journal:
    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT,"
            " at REAL, kind TEXT, data TEXT, undone INTEGER DEFAULT 0)"
        )
        os.chmod(path, 0o600)
        self._lock = threading.Lock()

    def record(self, turn_id: str, kind: str, **data: Any) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO actions (turn_id, at, kind, data) VALUES (?, ?, ?, ?)",
                (turn_id, time.time(), kind, json.dumps(data, default=str)),
            )

    def pending(self, turn_id: str) -> list[Action]:
        rows = self._db.execute(
            "SELECT id, turn_id, kind, data FROM actions WHERE turn_id = ? AND undone = 0 ORDER BY id",
            (turn_id,),
        ).fetchall()
        return [Action(r[0], r[1], r[2], json.loads(r[3])) for r in rows]

    def last_turn(self) -> str | None:
        row = self._db.execute(
            "SELECT turn_id FROM actions WHERE undone = 0 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def mark_undone(self, ids: list[int]) -> None:
        with self._lock:
            self._db.executemany("UPDATE actions SET undone = 1 WHERE id = ?", [(i,) for i in ids])

    def close(self) -> None:
        self._db.close()


async def undo_turn(journal: Journal, turn_id: str, ctx: ToolContext) -> tuple[bool, list[str]]:
    """Reverse a turn newest-first. Returns (all_ok, human descriptions of what was undone)."""
    done: list[int] = []
    undone: list[str] = []
    ok = True
    for action in reversed(journal.pending(turn_id)):
        fn = INVERSES.get(action.kind)
        if fn is None:
            continue
        try:
            await fn(action.data, ctx)
            done.append(action.id)
            undone.append(action.describe())
        except Exception as e:  # keep going: undo as much as possible
            ok = False
            undone.append(f"couldn't undo {action.describe()}: {e}")
    journal.mark_undone(done)
    return ok, undone
