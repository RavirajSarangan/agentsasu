"""Spotting "Hey Sasu" in a rough transcript (tiny Whisper often merges or misspells it). Pure.

Real outputs seen for "Hey Sasu": "Hesasul", "He Sasuo", "Heis azul", "Hey Sasuar", "சாசி".
So we match the *sound shape* s-a-s-u across word boundaries rather than exact words.
"""

from __future__ import annotations

import re

# s(h) + a/e vowel(s) + s/z/sh + u/o/a vowel  →  sasu, shasu, saasu, sazu, sashu, sesu, sasoo…
LATIN = re.compile(r"s[ae]{1,2}(?:s|z|sh)[uoa]|sh[ae]{1,2}s[uo]")  # also "Shasu" (Tamil-accented)
TAMIL = re.compile(r"(?:சா|ச)(?:சு|சி|ஸு|ஸ|சூ|சோ)")
# Whole short Tamil words that are "Sasu" with the last vowel swallowed: சாச, சாஸ், சச
TAMIL_SHORT = ("சாச", "சாஸ", "சச")
# Words Whisper hears when "Sasu" is said alone in other accents
LATIN_ALIASES = {"sauce", "sasse", "sassu", "saasu", "sasoo", "sassy", "sarsu"}
STOP_WORDS = ("stop", "wait", "enough", "nil", "niruthu", "nirutthu", "நிறுத்து", "போதும்", "pothum")
# Common words that contain the sound shape but aren't the wake word.
NOT_WAKE = {"season", "seasons", "sasha", "sausage", "sazon", "seashore", "seashell"}

_WORD = re.compile(r"[a-zA-Z0-9]+|[\u0B80-\u0BFF]+")


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _custom(words: list[str], names: tuple[str, ...]) -> tuple[bool, str]:
    """Match user-chosen robot names ("Chitti", "Kutty", "சிட்டி") within one edit."""
    for name in names:
        target = name.lower().replace(" ", "")
        if not target or target == "sasu":
            continue
        tamil = not target.isascii()
        for i in range(len(words)):
            for span in (1, 2):
                chunk = "".join(words[i : i + span])
                if tamil:
                    if chunk == target:
                        return True, " ".join(words[i + span :])
                elif (
                    (
                        len(target) >= 4
                        and abs(len(chunk) - len(target)) <= 1
                        and _edit_distance(chunk, target) <= 1
                    )
                    or len(target) < 4
                    and chunk == target
                ):
                    return True, " ".join(words[i + span :])
    return False, ""


def find_wake(text: str, names: tuple[str, ...] = ()) -> tuple[bool, str]:
    """(heard the robot's name, whatever was said after it). "Sasu" always works."""
    words = [w for w in _WORD.findall(text.lower()) if w not in NOT_WAKE]
    if names:
        heard, rest = _custom(words, names)
        if heard:
            return heard, rest
    for i, w in enumerate(words):
        if TAMIL.search(w) or (w.startswith(TAMIL_SHORT) and len(w) <= 5) or w in LATIN_ALIASES:
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
