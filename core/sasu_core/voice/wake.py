"""Spotting "Hey Sasu" in a rough transcript (tiny Whisper often merges or misspells it). Pure.

Real outputs seen for "Hey Sasu": "Hesasul", "He Sasuo", "Heis azul", "Hey Sasuar", "சாசி".
So we match the *sound shape* s-a-s-u across word boundaries rather than exact words.
"""

from __future__ import annotations

import re

# s + a/e vowel(s) + s/z/sh + u/o/a vowel  →  sasu, saasu, sazu, sashu, sesu, sasoo…
LATIN = re.compile(r"s[ae]{1,2}(?:s|z|sh)[uoa]")
TAMIL = re.compile(r"(?:சா|ச)(?:சு|சி|ஸு|ஸ|சூ|சோ)")
STOP_WORDS = ("stop", "wait", "enough", "nil", "niruthu", "nirutthu", "நிறுத்து", "போதும்", "pothum")
# Common words that contain the sound shape but aren't the wake word.
NOT_WAKE = {"season", "seasons", "sasha", "sausage", "sazon", "seashore", "seashell"}

_WORD = re.compile(r"[a-zA-Z0-9]+|[\u0B80-\u0BFF]+")


def find_wake(text: str) -> tuple[bool, str]:
    """(heard "Sasu", whatever was said after it)."""
    words = [w for w in _WORD.findall(text.lower()) if w not in NOT_WAKE]
    for i, w in enumerate(words):
        if TAMIL.search(w):
            return True, " ".join(words[i + 1 :])
    # Join neighbours too: "sa su", "heis azul" → "heisazul"
    for i in range(len(words)):
        for span in (1, 2, 3):
            chunk = "".join(words[i : i + span])
            if span > 1 and len(chunk) > 12:
                break
            if LATIN.search(chunk):
                return True, " ".join(words[i + span :])
    return False, ""


def is_stop(text: str) -> bool:
    toks = set(_WORD.findall(text.lower()))
    return any(w in toks or w in text for w in STOP_WORDS) and len(toks) <= 4
