"""Tamil Panchangam, worked out on the Mac: "Inniku Rahu kaalam eppo?", "enna thithi?".

- Sunrise / sunset: NOAA's solar equations for the home city (±1–2 min), in the city's
  own time zone (Open-Meteo geocoding gives lat/lon/zone; cached in place.json).
- Rahu kaalam, Yamagandam, Kuligai: the daytime cut into 8 equal parts, picked by weekday.
- Abhijit muhurtham: the 8th of 15 equal parts of the daytime (around local noon).
- Tamil month and day: the sun's sidereal sign at sunset (Lahiri ayanamsa); day 1 is the
  first day whose sunset falls in the new sign.
- Thithi: the moon's lead over the sun in 12° steps, at sunrise (Meeus' short series,
  ~0.3° — boundaries can be off by under an hour).
No city set: 6:00–18:00 local, and the answer says it's approximate.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

# part of the 8-part day (1-based), Monday..Sunday
RAHU = [2, 7, 5, 6, 4, 3, 8]
YAMA = [4, 3, 2, 1, 7, 6, 5]
KULIGAI = [6, 5, 4, 3, 2, 1, 7]

MONTHS_EN = ["Chithirai", "Vaikasi", "Aani", "Aadi", "Avani", "Purattasi", "Aippasi", "Karthigai", "Margazhi", "Thai", "Maasi", "Panguni"]  # fmt: skip
MONTHS_TA = ["சித்திரை", "வைகாசி", "ஆனி", "ஆடி", "ஆவணி", "புரட்டாசி", "ஐப்பசி", "கார்த்திகை", "மார்கழி", "தை", "மாசி", "பங்குனி"]  # fmt: skip
THITHI_EN = ["Prathamai", "Dwitiyai", "Tritiyai", "Chaturthi", "Panchami", "Shashti", "Saptami", "Ashtami", "Navami", "Dasami", "Ekadasi", "Dwadasi", "Trayodasi", "Chaturdasi"]  # fmt: skip
THITHI_TA = ["பிரதமை", "துவிதியை", "திருதியை", "சதுர்த்தி", "பஞ்சமி", "சஷ்டி", "சப்தமி", "அஷ்டமி", "நவமி", "தசமி", "ஏகாதசி", "துவாதசி", "திரயோதசி", "சதுர்த்தசி"]  # fmt: skip

ASK = re.compile(
    r"\b(?:ra[ah]u|raagu|ragu)\s*(?:kaa?lam|kalam|kaalam)|\byama\s*ga?ndam|\bemagandam|\b(?:kuligai|gulika)"
    r"|\bnalla\s+neram|\b(?:thithi|tithi|thidhi)\b|\btamil\s+(?:date|month|maasam|masam|thethi)"
    r"|\bpanchang(?:am)?\b|ராகு|எமகண்டம்|குளிகை|நல்ல\s*நேரம்|திதி|பஞ்சாங்கம்|தமிழ்\s*தேதி",
    re.IGNORECASE,
)
TOMORROW = re.compile(r"\b(?:tomorrow|naa?laikk?u|naalaiku)\b|நாளை", re.IGNORECASE)


@dataclass
class Place:
    city: str
    lat: float
    lon: float
    tz: str


@dataclass
class Day:
    date: date
    place: Place | None
    sunrise: datetime
    sunset: datetime
    rahu: tuple[datetime, datetime]
    yama: tuple[datetime, datetime]
    kuligai: tuple[datetime, datetime]
    abhijit: tuple[datetime, datetime]
    month: int  # 0 = Chithirai
    month_day: int
    thithi: int  # 1..30 (15 Pournami, 30 Amavasai)

    @property
    def approximate(self) -> bool:
        return self.place is None


# ── astronomy ──────────────────────────────────────────────────────────────


def _sun_minutes(d: date, lat: float, lon: float) -> tuple[float, float]:
    """(sunrise, sunset) in minutes after 00:00 UTC on `d` (NOAA general solar position)."""
    doy = d.timetuple().tm_yday
    g = 2 * math.pi / 365 * (doy - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))  # fmt: skip
    decl = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)  # fmt: skip
    la = math.radians(lat)
    x = math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl)) - math.tan(la) * math.tan(
        decl
    )
    ha = math.degrees(math.acos(max(-1.0, min(1.0, x))))
    return 720 - 4 * (lon + ha) - eqtime, 720 - 4 * (lon - ha) - eqtime


def _jd(t: datetime) -> float:
    return t.timestamp() / 86400 + 2440587.5


def sun_longitude(t: datetime) -> float:
    d = _jd(t) - 2451545.0
    L = 280.460 + 0.9856474 * d
    g = math.radians(357.528 + 0.9856003 * d)
    return (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360


def moon_longitude(t: datetime) -> float:
    d = _jd(t) - 2451545.0
    Lm = 218.316 + 13.176396 * d
    Mm = math.radians(134.963 + 13.064993 * d)
    Ms = math.radians(357.529 + 0.98560028 * d)
    D = math.radians(297.850 + 12.190749 * d)
    F = math.radians(93.272 + 13.229350 * d)
    lon = (
        Lm
        + 6.289 * math.sin(Mm)
        - 1.274 * math.sin(Mm - 2 * D)
        + 0.658 * math.sin(2 * D)
        + 0.214 * math.sin(2 * Mm)
        - 0.186 * math.sin(Ms)
        - 0.114 * math.sin(2 * F)
    )
    return lon % 360


def ayanamsa(t: datetime) -> float:
    """Lahiri, linear around J2000 (good to a few arc-seconds this century)."""
    years = (_jd(t) - 2451545.0) / 365.25
    return 23.853 + years * 50.29 / 3600


def sign(t: datetime) -> int:
    return int(((sun_longitude(t) - ayanamsa(t)) % 360) // 30)


def thithi_at(t: datetime) -> int:
    return int(((moon_longitude(t) - sun_longitude(t)) % 360) // 12) + 1


# ── the day ────────────────────────────────────────────────────────────────


def _span(start: datetime, part: timedelta, n: int) -> tuple[datetime, datetime]:
    return start + part * (n - 1), start + part * n


def _sun_times(d: date, place: Place | None, tz: ZoneInfo) -> tuple[datetime, datetime]:
    if place is None:
        return datetime(d.year, d.month, d.day, 6, tzinfo=tz), datetime(
            d.year, d.month, d.day, 18, tzinfo=tz
        )
    rise, set_ = _sun_minutes(d, place.lat, place.lon)
    midnight = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return (midnight + timedelta(minutes=rise)).astimezone(tz), (
        midnight + timedelta(minutes=set_)
    ).astimezone(tz)


def day(d: date, place: Place | None, local_tz: str | None = None) -> Day:
    tz = ZoneInfo(place.tz if place else (local_tz or "UTC"))
    rise, set_ = _sun_times(d, place, tz)
    part = (set_ - rise) / 8
    wd = d.weekday()
    month = sign(set_)
    n = 1
    while n < 33 and sign(_sun_times(d - timedelta(days=n), place, tz)[1]) == month:
        n += 1
    return Day(
        date=d,
        place=place,
        sunrise=rise,
        sunset=set_,
        rahu=_span(rise, part, RAHU[wd]),
        yama=_span(rise, part, YAMA[wd]),
        kuligai=_span(rise, part, KULIGAI[wd]),
        abhijit=_span(rise, (set_ - rise) / 15, 8),
        month=month,
        month_day=n,
        thithi=thithi_at(rise),
    )


# ── words ──────────────────────────────────────────────────────────────────


def hm(t: datetime) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'PM' if t.hour >= 12 else 'AM'}"


def span(s: tuple[datetime, datetime]) -> str:
    return f"{hm(s[0])}–{hm(s[1])}"


def iso(s: tuple[datetime, datetime]) -> list[str]:
    return [s[0].isoformat(), s[1].isoformat()]


def thithi_name(n: int, lang: str) -> str:
    if n == 15:
        return "பௌர்ணமி" if lang == "ta" else "Pournami (full moon)"
    if n == 30:
        return "அமாவாசை" if lang == "ta" else "Amavasai (new moon)"
    k = (n - 1) % 15
    if lang == "ta":
        return f"{'வளர்பிறை' if n < 15 else 'தேய்பிறை'} {THITHI_TA[k]}"
    return f"{'Valarpirai' if n < 15 else 'Theipirai'} {THITHI_EN[k]}"


def tamil_date(dd: Day, lang: str) -> str:
    return f"{MONTHS_TA[dd.month] if lang == 'ta' else MONTHS_EN[dd.month]} {dd.month_day}"


def answer(text: str, dd: Day, lang: str) -> str:
    """What to say for an ask: the parts asked about (all of them for "panchangam")."""
    t = text.lower()
    ta = lang == "ta"
    when = (
        ("நாளைக்கு" if ta else "Tomorrow")
        if TOMORROW.search(text)
        else ("இன்னைக்கு" if ta else "Today")
    )
    parts: list[str] = []
    wants_all = bool(re.search(r"panchang|பஞ்சாங்கம்", t))
    if wants_all or re.search(r"ra[ah]u|raagu|ragu|ராகு", t):
        parts.append(f"ராகு காலம் {span(dd.rahu)}" if ta else f"Rahu kaalam {span(dd.rahu)}")
    if wants_all or re.search(r"yama|emagand|எமகண்டம்", t):
        parts.append(f"எமகண்டம் {span(dd.yama)}" if ta else f"Yamagandam {span(dd.yama)}")
    if wants_all or re.search(r"kuligai|gulika|குளிகை", t):
        parts.append(f"குளிகை {span(dd.kuligai)}" if ta else f"Kuligai {span(dd.kuligai)}")
    if re.search(r"nalla|நல்ல", t):
        parts.append(
            f"அபிஜித் முகூர்த்தம் {span(dd.abhijit)}. ராகு காலம் {span(dd.rahu)}, எமகண்டம் {span(dd.yama)} தவிர்க்கவும்"
            if ta
            else f"Abhijit muhurtham {span(dd.abhijit)}. Avoid Rahu kaalam {span(dd.rahu)} and Yamagandam {span(dd.yama)}"
        )
    if wants_all or re.search(r"thithi|tithi|thidhi|திதி|tamil|தமிழ்", t):
        parts.append(f"{tamil_date(dd, lang)}, {thithi_name(dd.thithi, lang)}")
    text_ = f"{when}: " + ". ".join(parts) + "."
    if dd.approximate:
        text_ += (
            " (தோராயமா — Settings-ல ஊர் போடுங்க.)"
            if ta
            else " These are approximate: set your city in Settings for exact times."
        )
    return text_


def briefing_line(dd: Day, lang: str) -> str:
    return (
        f"இன்னைக்கு ராகு காலம் {span(dd.rahu)}, {thithi_name(dd.thithi, 'ta')}."
        if lang == "ta"
        else f"Rahu kaalam today is {span(dd.rahu)}; it's {thithi_name(dd.thithi, 'en')}."
    )


def local_zone() -> str:
    """The Mac's own IANA time zone (for the no-city fallback)."""
    import os

    path = os.path.realpath("/etc/localtime")
    return path.split("zoneinfo/", 1)[1] if "zoneinfo/" in path else "UTC"


# ── place ──────────────────────────────────────────────────────────────────


async def geocode(city: str, transport: httpx.AsyncBaseTransport | None = None) -> Place | None:
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
            h = hits[0]
            return Place(
                h["name"],
                float(h["latitude"]),
                float(h["longitude"]),
                str(h.get("timezone") or "UTC"),
            )
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


class PlaceCache:
    """The home city's coordinates, looked up once (only the city name ever leaves the Mac)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, city: str) -> Place | None:
        try:
            d = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return None
        return Place(**d["place"]) if d.get("city") == city.strip().lower() else None

    def put(self, city: str, place: Place) -> None:
        self.path.write_text(json.dumps({"city": city.strip().lower(), "place": place.__dict__}))
