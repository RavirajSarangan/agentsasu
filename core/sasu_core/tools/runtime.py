"""Running processes for tools: never through a shell, always with a timeout."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Proc:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


Runner = Callable[[Sequence[str], float, str | None], Awaitable[Proc]]


async def run(args: Sequence[str], timeout: float = 15.0, stdin: str | None = None) -> Proc:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin is not None else None), timeout
        )
    except TimeoutError:
        proc.kill()
        return Proc(124, "", "timed out")
    return Proc(proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace"))


def applescript(*lines: str) -> list[str]:
    """osascript args. User data must go in argv (`item n of argv`), never in the script."""
    args = ["osascript", "-e", "on run argv"]
    for line in lines:
        args += ["-e", line]
    return [*args, "-e", "end run"]
