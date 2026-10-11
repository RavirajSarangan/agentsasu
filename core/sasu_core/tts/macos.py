"""Speech with the Mac's built-in voices: zero downloads.

Tamil script → Vani (ta_IN); everything else → Rishi (en_IN). A Tanglish reply switches
voice per run of script, so each part sounds natural. Cancelling kills `say` at once.
"""

from __future__ import annotations

import asyncio
import re
import shutil

TAMIL = re.compile(r"[஀-௿]")
VOICES = {"ta": "Vani", "en": "Rishi"}


def split_runs(text: str) -> list[tuple[str, str]]:
    """[(lang, chunk)] where each chunk is a sentence-ish run in one script."""
    parts = re.split(r"(?<=[.!?।])\s+", text.strip())
    runs: list[tuple[str, str]] = []
    for part in parts:
        if not part:
            continue
        lang = "ta" if TAMIL.search(part) else "en"
        if runs and runs[-1][0] == lang:
            runs[-1] = (lang, runs[-1][1] + " " + part)
        else:
            runs.append((lang, part))
    return runs


class Speaker:
    def __init__(self, rate: int = 190) -> None:
        self.rate = rate
        self.enabled = shutil.which("say") is not None
        self._proc: asyncio.subprocess.Process | None = None

    async def say(self, text: str) -> None:
        if not self.enabled:
            return
        for lang, chunk in split_runs(text):
            self._proc = await asyncio.create_subprocess_exec(
                "say", "-v", VOICES[lang], "-r", str(self.rate), chunk,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            try:
                await self._proc.wait()
            finally:
                self._proc = None

    def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
