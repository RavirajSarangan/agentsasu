"""Tamil Panchangam: astronomy anchors, the weekday tables, answers, briefing, alert, API."""

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from sasu_core import panchangam as P
from tests.conftest import TOKEN
from tests.test_bundle_h import Mac, said, until

CHENNAI = P.Place("Chennai", 13.0827, 80.2707, "Asia/Kolkata")
IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    ("d", "thithi"),
    [(date(2026, 2, 17), 30), (date(2026, 8, 12), 30), (date(2026, 3, 3), 15)],  # eclipse days
)
def test_new_and_full_moons(d: date, thithi: int) -> None:
    assert P.day(d, CHENNAI).thithi == thithi


@pytest.mark.parametrize(
    ("d", "month", "n"),
    [
        (date(2026, 1, 14), "Thai", 1),  # Pongal
        (date(2026, 1, 13), "Margazhi", 29),
        (date(2026, 4, 14), "Chithirai", 1),  # Tamil New Year
        (date(2026, 4, 13), "Panguni", 30),
    ],
)
def test_tamil_months(d: date, month: str, n: int) -> None:
    dd = P.day(d, CHENNAI)
    assert (P.MONTHS_EN[dd.month], dd.month_day) == (month, n)


def test_chennai_sunrise_and_sunset() -> None:
    dd = P.day(date(2026, 2, 17), CHENNAI)
    assert dd.sunrise.tzinfo is not None
    assert abs((dd.sunrise - datetime(2026, 2, 17, 6, 33, tzinfo=IST)).total_seconds()) < 300
    assert abs((dd.sunset - datetime(2026, 2, 17, 18, 17, tzinfo=IST)).total_seconds()) < 300


TEXTBOOK = {  # Monday..Sunday with a 6:00–18:00 day
    "rahu": ["7:30 AM–9:00 AM", "3:00 PM–4:30 PM", "12:00 PM–1:30 PM", "1:30 PM–3:00 PM", "10:30 AM–12:00 PM", "9:00 AM–10:30 AM", "4:30 PM–6:00 PM"],
    "yama": ["10:30 AM–12:00 PM", "9:00 AM–10:30 AM", "7:30 AM–9:00 AM", "6:00 AM–7:30 AM", "3:00 PM–4:30 PM", "1:30 PM–3:00 PM", "12:00 PM–1:30 PM"],
    "kuligai": ["1:30 PM–3:00 PM", "12:00 PM–1:30 PM", "10:30 AM–12:00 PM", "9:00 AM–10:30 AM", "7:30 AM–9:00 AM", "6:00 AM–7:30 AM", "3:00 PM–4:30 PM"],
}  # fmt: skip


@pytest.mark.parametrize("wd", range(7))
def test_weekday_tables_match_the_textbook(wd: int) -> None:
    d = date(2026, 10, 12) + timedelta(days=wd)  # a Monday, then the week
    dd = P.day(d, None, "Asia/Kolkata")
    assert dd.approximate
    for key in ("rahu", "yama", "kuligai"):
        assert P.span(getattr(dd, key)) == TEXTBOOK[key][wd], key
    assert P.span(dd.abhijit) == "11:36 AM–12:24 PM"


def test_answers() -> None:
    dd = P.day(date(2026, 10, 12), CHENNAI)
    en = P.answer("inniku rahu kaalam eppo", dd, "en")
    assert en.startswith("Today: Rahu kaalam ") and "approximate" not in en
    ta = P.answer("நாளைக்கு ராகு காலம் எப்போ", dd, "ta")
    assert ta.startswith("நாளைக்கு: ராகு காலம் ")
    assert P.answer("inniku enna thithi", dd, "en") == "Today: Purattasi 26, Valarpirai Dwitiyai."
    nalla = P.answer("nalla neram eppo", dd, "en")
    assert "Abhijit muhurtham" in nalla and "Avoid Rahu kaalam" in nalla
    full = P.answer("panchangam sollu", dd, "ta")
    assert all(w in full for w in ("ராகு காலம்", "எமகண்டம்", "குளிகை", "புரட்டாசி"))
    assert "approximate" in P.answer("rahu kaalam", P.day(date(2026, 10, 12), None, "UTC"), "en")


@pytest.mark.parametrize(
    "text",
    [
        "inniku rahu kaalam eppo",
        "naalaikku ragu kalam",
        "nalla neram eppo",
        "enna thithi",
        "tamil date sollu",
        "இன்னைக்கு ராகு காலம்",
        "panchangam",
    ],
)
def test_ask(text: str) -> None:
    assert P.ASK.search(text)


class Geo:
    def __init__(self) -> None:
        self.calls = 0

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            if "geocoding" in req.url.host:
                self.calls += 1
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "name": "Chennai",
                                "latitude": 13.0827,
                                "longitude": 80.2707,
                                "timezone": "Asia/Kolkata",
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        return httpx.MockTransport(handler)


def setup(client: TestClient, now: datetime) -> tuple[Any, Geo]:
    core = client.app.state.core  # type: ignore[attr-defined]
    core.runner = Mac()
    geo = Geo()
    core.transport = geo.transport()
    core.settings.city = "Chennai"
    core.clock = lambda: now.timestamp()
    return core, geo


def test_voice_answer_and_place_cache(bare_client: TestClient) -> None:
    core, geo = setup(bare_client, datetime(2026, 10, 12, 8, 0, tzinfo=IST))
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        for text in ("inniku rahu kaalam eppo", "இன்னைக்கு என்ன திதி"):
            ws.send_text(json.dumps({"type": "text_command", "text": text}))
            events = until(ws, "turn_done")
    assert said(events) == "இன்னைக்கு: புரட்டாசி 26, வளர்பிறை துவிதியை."
    assert geo.calls == 1  # looked up once, then cached in place.json
    assert json.loads(core.places.path.read_text())["place"]["tz"] == "Asia/Kolkata"


def test_briefing_has_rahu_kaalam(bare_client: TestClient) -> None:
    setup(bare_client, datetime(2026, 10, 12, 7, 0, tzinfo=IST))
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        ws.send_text(json.dumps({"type": "text_command", "text": "good morning"}))
        events = until(ws, "turn_done")
    assert "Rahu kaalam today is 7:27 AM–8:56 AM" in said(events)


def test_rahu_alert_once(bare_client: TestClient) -> None:
    core, _ = setup(bare_client, datetime(2026, 10, 12, 7, 24, tzinfo=IST))
    core.settings.rahu_alert = True
    with bare_client.websocket_connect(f"/ws?t={TOKEN}") as ws:
        until(ws, "voice_status")
        bare_client.portal.call(core.rahu_tick)  # type: ignore[union-attr]
        events = until(ws, "say_end")
        bare_client.portal.call(core.rahu_tick)  # type: ignore[union-attr]
    assert said(events).startswith("ராகு காலம் 5 நிமிஷத்துல ஆரம்பிக்குது")
    assert core._rahu_warned == date(2026, 10, 12)
    core.clock = lambda: datetime(2026, 10, 12, 7, 10, tzinfo=IST).timestamp()
    core._rahu_warned = None
    bare_client.portal.call(core.rahu_tick)  # type: ignore[union-attr]
    assert core._rahu_warned is None  # 17 minutes before: too early


def test_api(bare_client: TestClient) -> None:
    setup(bare_client, datetime(2026, 10, 12, 9, 0, tzinfo=IST))
    r = bare_client.get("/api/panchangam", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert r["city"] == "Chennai" and r["approximate"] is False
    assert r["tamil"] == {"en": "Purattasi 26", "ta": "புரட்டாசி 26"} and r["thithi"]["n"] == 2
    assert r["rahu"][0].startswith("2026-10-12T07:27")
