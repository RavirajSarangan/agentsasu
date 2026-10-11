"""“Good morning” briefing: time, weather, today's calendar and reminders, battery.

Works without an AI key. Weather comes from Open-Meteo (free, no key, no account).
Calendar and Reminders are read-only AppleScript, best effort.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .tools.runtime import Runner, applescript

TRIGGER = re.compile(
    r"\b(?:good\s*morning|briefing|what'?s\s+my\s+day|kaalai\s+vanakkam)\b|காலை\s*வணக்கம்",
    re.IGNORECASE,
)

WMO = {
    0: ("clear sky", "தெளிவான வானம்"),
    1: ("mostly clear", "பெரும்பாலும் தெளிவு"),
    2: ("partly cloudy", "மேகமூட்டம்"),
    3: ("cloudy", "மேகமூட்டம்"),
    45: ("foggy", "பனிமூட்டம்"),
    51: ("light drizzle", "லேசான தூறல்"),
    61: ("light rain", "லேசான மழை"),
    63: ("rain", "மழை"),
    65: ("heavy rain", "கனமழை"),
    80: ("showers", "மழைச்சாரல்"),
    95: ("thunderstorms", "இடியுடன் மழை"),
}


def describe(code: int, lang: str) -> str:
    key = max((k for k in WMO if k <= code), default=0)
    en, ta = WMO[key]
    return ta if lang == "ta" else en


async def weather(
    city: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any] | None:
    if not city.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=6, transport=transport) as c:
            g = await c.get(
                "https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}
            )
            hits = g.json().get("results") or []
            if not hits:
                return None
            w = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": hits[0]["latitude"],
                    "longitude": hits[0]["longitude"],
                    "current": "temperature_2m,weather_code",
                    "daily": "temperature_2m_max,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 1,
                },
            )
            d = w.json()
            return {
                "city": hits[0]["name"],
                "temp": round(d["current"]["temperature_2m"]),
                "code": int(d["current"]["weather_code"]),
                "max": round(d["daily"]["temperature_2m_max"][0]),
                "rain": int(d["daily"]["precipitation_probability_max"][0] or 0),
            }
    except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError):
        return None


EVENTS_SCRIPT = applescript(
    "set out to {}",
    "set t0 to current date",
    "set hours of t0 to 0",
    "set minutes of t0 to 0",
    "set seconds of t0 to 0",
    "set t1 to t0 + (1 * days)",
    'tell application "Calendar"',
    "repeat with c in calendars",
    "repeat with e in (every event of c whose start date ≥ t0 and start date < t1)",
    'set end of out to ((time string of (start date of e)) & " " & (summary of e))',
    "end repeat",
    "end repeat",
    "end tell",
    "set AppleScript's text item delimiters to linefeed",
    "return out as text",
)

REMINDERS_SCRIPT = applescript(
    'tell application "Reminders" to set r to name of (every reminder whose completed is false)',
    "set AppleScript's text item delimiters to linefeed",
    "return r as text",
)


async def gather(
    run: Runner, city: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    events = (await run(EVENTS_SCRIPT, 8, None)).out.strip()
    todos = (await run(REMINDERS_SCRIPT, 8, None)).out.strip()
    batt = (await run(["pmset", "-g", "batt"], 5, None)).out
    m = re.search(r"(\d+)%", batt)
    return {
        "events": [e for e in events.splitlines() if e.strip()][:5],
        "todos": [t for t in todos.splitlines() if t.strip()][:5],
        "battery": int(m.group(1)) if m else None,
        "weather": await weather(city, transport),
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def compose(
    info: dict[str, Any], lang: str, name: str = "", now: time.struct_time | None = None
) -> str:
    now = now or time.localtime()
    clock = time.strftime("%-I:%M %p", now)
    day = time.strftime("%A, %-d %B", now)
    w = info.get("weather")
    ev: list[str] = info.get("events") or []
    todos: list[str] = info.get("todos") or []
    batt = info.get("battery")
    if lang == "ta":
        greet = "காலை வணக்கம்" if now.tm_hour < 12 else "வணக்கம்"
        parts = [f"{greet}{' ' + name if name else ''}! இப்போ {clock}, {day}."]
        if w:
            parts.append(
                f"{w['city']}-ல {w['temp']}°, {describe(w['code'], 'ta')}. மழை வாய்ப்பு {w['rain']}%."
            )
        parts.append(
            f"இன்னைக்கு {len(ev)} meeting இருக்கு. முதல்: {ev[0]}."
            if ev
            else "இன்னைக்கு meeting எதுவும் இல்ல."
        )
        if todos:
            parts.append(f"{len(todos)} reminder பாக்கி இருக்கு.")
        if batt is not None and batt < 30:
            parts.append(f"Battery {batt}% தான், charge போடுங்க.")
        parts.append("நல்ல நாளா அமையட்டும்!")
    else:
        greet = (
            "Good morning"
            if now.tm_hour < 12
            else "Good afternoon"
            if now.tm_hour < 17
            else "Good evening"
        )
        parts = [f"{greet}{', ' + name if name else ''}! It's {clock}, {day}."]
        if w:
            parts.append(
                f"In {w['city']} it's {w['temp']} degrees and {describe(w['code'], 'en')}, "
                f"up to {w['max']}, with a {w['rain']}% chance of rain."
            )
        parts.append(
            f"You have {_plural(len(ev), 'event')} today. First up: {ev[0]}."
            if ev
            else "Your calendar is clear today."
        )
        if todos:
            parts.append(f"{_plural(len(todos), 'reminder')} still open.")
        if batt is not None and batt < 30:
            parts.append(f"Battery is at {batt}%, plug in when you can.")
        parts.append("Have a great day!")
    return " ".join(parts)
