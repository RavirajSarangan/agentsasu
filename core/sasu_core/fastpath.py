"""Instant commands: common requests run locally, without waiting for the AI.

"paattu podu", "next song", "volume 30", "Safari open pannu", "மணி என்ன" … are parsed
here in English, Tanglish and Tamil. They still go through the Executor, so policy,
undo journal and audit apply exactly as for AI-planned calls.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

WAKE_PREFIX = re.compile(
    r"^\s*(?:hey|hi|ok|okay|he)?[\s,]*(?:sasu|saasu|sashu|சாசு)[\s,.!]*", re.IGNORECASE
)

SITES = {
    "google": "google.com",
    "youtube": "youtube.com",
    "gmail": "mail.google.com",
    "github": "github.com",
    "whatsapp": "web.whatsapp.com",
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "netflix": "netflix.com",
    "chatgpt": "chatgpt.com",
    "maps": "maps.google.com",
    "linkedin": "linkedin.com",
    "x": "x.com",
    "twitter": "x.com",
}
APP_ALIASES = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "spotify": "Spotify",
    "music": "Music",
    "finder": "Finder",
    "notes": "Notes",
    "calendar": "Calendar",
    "mail": "Mail",
    "messages": "Messages",
    "whatsapp app": "WhatsApp",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "terminal": "Terminal",
    "settings": "System Settings",
    "system settings": "System Settings",
    "photos": "Photos",
    "camera": "Photo Booth",
    "calculator": "Calculator",
    "reminders": "Reminders",
    "slack": "Slack",
    "zoom": "zoom.us",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "teams": "Microsoft Teams",
    "figma": "Figma",
}

TAMIL_NUM = str.maketrans("௦௧௨௩௪௫௬௭௮௯", "0123456789")


@dataclass
class Fast:
    """One instant command: tool calls to run, and what to say (en / ta)."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    say_en: str = ""
    say_ta: str = ""
    kind: str = ""


def _clean(text: str) -> str:
    t = WAKE_PREFIX.sub("", text.strip()).translate(TAMIL_NUM)
    t = re.sub(r"[.!?,]+$", "", t).strip()
    return re.sub(r"\s+", " ", t)


def _has(t: str, *pats: str) -> bool:
    return any(re.search(p, t, re.IGNORECASE) for p in pats)


def parse(text: str) -> Fast | None:
    t = _clean(text)
    low = t.lower()
    if not low or len(low.split()) > 9:
        return None

    # ── music ──
    if _has(low, r"\b(next|skip)\b( (song|track|paattu|one))?\b", r"அடுத்த\s*பாட்டு", r"next\s*podu"):
        return Fast([("media_control", {"action": "next"})], "Next song.", "அடுத்த பாட்டு.", "music")
    if _has(low, r"\b(previous|last|before)\s+(song|track)\b", r"munnadi\s*paattu", r"முந்தைய"):
        return Fast(
            [("media_control", {"action": "previous"})], "Going back.", "முந்தைய பாட்டு.", "music"
        )
    if _has(
        low,
        r"\b(pause|stop)\b.*\b(music|song|spotify|paattu)\b",
        r"^(pause|pause it|stop music)$",
        r"paattu\s*niruthu",
        r"பாட்ட?ை?\s*நிறுத்து",
    ):
        return Fast([("media_control", {"action": "pause"})], "Paused.", "நிறுத்திட்டேன்.", "music")
    if _has(
        low,
        r"\bplay\b.*\b(music|song|songs|spotify|something)\b",
        r"^play$",
        r"^resume",
        r"(paattu|music|song)\s*(podu|potu|play pannu)",
        r"பாட்டு\s*போடு",
        r"^(பாட்டு|paattu|music|songs?)$",
    ):
        return Fast([("media_control", {"action": "play"})], "Playing.", "பாட்டு போடறேன்.", "music")

    # ── volume ──
    m = re.search(
        r"(?:volume|sound|சத்தம்)\D{0,8}?(\d{1,3})|(\d{1,3})\s*(?:%|percent)?\s*(?:volume|sound)", low
    )
    if m:
        level = max(0, min(100, int(m.group(1) or m.group(2))))
        return Fast(
            [("system_volume", {"level": level})], f"Volume {level}.", f"சத்தம் {level}.", "volume"
        )
    if _has(
        low,
        r"\b(louder|volume up|increase (the )?volume|turn it up)\b",
        r"(sound|volume|sa(?:t|th)+am)\s*(jaasti|athigam|ethu|kootu)",
        r"ச(த்)?தம்?\s*(அதிக|கூட்டு)",
    ):
        return Fast([("system_volume_step", {"delta": 15})], "Louder.", "சத்தம் கூட்டிட்டேன்.", "volume")
    if _has(
        low,
        r"\b(quieter|softer|volume down|lower (the )?volume|turn it down)\b",
        r"(sound|volume|sa(?:t|th)+am)\s*(konjam\s*)?(kammi|korai|kurai|kurey)",
        r"konjam\s*kammi",
        r"ச(த்)?தம்?\s*(குறை|கம்மி|க)",
    ):
        return Fast(
            [("system_volume_step", {"delta": -15})], "Quieter.", "சத்தம் குறைச்சிட்டேன்.", "volume"
        )
    if _has(low, r"^(mute|mute it|silence)$", r"\bmute\b"):
        return Fast([("system_volume", {"level": 0})], "Muted.", "சத்தம் இல்லாம பண்ணிட்டேன்.", "volume")

    # ── dark mode ──
    if _has(low, r"\bdark mode\b") and not _has(low, r"\boff\b"):
        return Fast(
            [("system_dark_mode", {"on": True})], "Dark mode on.", "Dark mode போட்டாச்சு.", "dark"
        )
    if _has(low, r"\blight mode\b", r"dark mode\s*off"):
        return Fast(
            [("system_dark_mode", {"on": False})], "Light mode on.", "Light mode போட்டாச்சு.", "dark"
        )

    # ── time / date / battery ──
    if _has(
        low,
        r"\bwhat('?s| is)? the time\b",
        r"^time\??$",
        r"\btime (enna|ennachu)\b",
        r"mani\s*enna",
        r"மணி\s*என்ன",
    ):
        now = time.strftime("%-I:%M %p")
        return Fast([], f"It's {now}.", f"இப்போ மணி {now}.", "time")
    if _has(
        low,
        r"\bwhat('?s| is)? (the )?(date|day)( today)?\b",
        r"inniku\s*(enna\s*)?(date|thethi)",
        r"இன்னைக்கு\s*என்ன\s*தேதி",
    ):
        today = time.strftime("%A, %-d %B")
        return Fast([], f"Today is {today}.", f"இன்னைக்கு {today}.", "date")
    if _has(low, r"\bbattery\b", r"charge\s*(evlo|evvalavu)", r"சார்ஜ்"):
        return Fast([("system_info", {})], "", "", "battery")

    # ── open app / site ──
    m = re.match(
        r"^(?:please\s+|can you\s+)?(?:open|launch|start)\s+(?:up\s+)?(?:the\s+)?(.+?)(?:\s+app)?$",
        low,
    ) or re.match(
        r"^(.+?)(?:\s*-?\s*(?:ai|ah|a|ஐ|ஐ))?\s+(?:open|opan|thora|thira|திற)\s*(?:pannu|panu|pannunga|பண்ணு)?$",
        low,
    )
    if m:
        target = m.group(1).strip(" -")
        if target in SITES or re.search(r"\.(com|org|net|io|in|lk|uk|dev|app)\b", target):
            url = SITES.get(target, target)
            return Fast(
                [("web_open", {"url": url})],
                f"Opening {target.title() if target in SITES else url}.",
                f"{target} திறக்கிறேன்.",
                "open",
            )
        app = APP_ALIASES.get(target)
        if (
            app is None
            and 0 < len(target.split()) <= 3
            and not re.search(r"\b(file|folder|my|the|all|every)\b", target)
        ):
            app = target.title()
        if app:
            return Fast(
                [("apps_open", {"app": app})], f"Opening {app}.", f"{app} திறக்கிறேன்.", "open"
            )
    return None


def battery_reply(content: str, lang: str) -> str:
    m = re.search(r"Battery: (\d+)%", content)
    if not m:
        return "I couldn't read the battery." if lang != "ta" else "Battery பார்க்க முடியல."
    pct = m.group(1)
    charging = "charging" in content.lower() and "discharging" not in content.lower()
    if lang == "ta":
        return f"Battery {pct} சதவீதம்{', charge ஆகுது' if charging else ''}."
    return f"Battery is at {pct} percent{', charging' if charging else ''}."
