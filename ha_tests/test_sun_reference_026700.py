"""0.26.7.0 UI hotfix: an independent reference for the house map's sun arc.

The weather window of the house map computes sunrise and sunset of the shown day in the browser (NOAA sunrise equation,
freshairiq-house-weather.js ``sunEvents``). Its browser test compares those times with
``frontend_tests/fixtures/sun_reference.json``; this test proves that every value in that file is what astral – the library
Home Assistant's sun integration itself uses – computes for the same place and day. Summer, winter, both daylight-saving
changes, the equator, polar day and polar night.
"""
from __future__ import annotations

import datetime
import json
import zoneinfo
from pathlib import Path

from astral import Observer
from astral.sun import elevation, sunrise, sunset

FIXTURE = Path(__file__).resolve().parents[1] / "frontend_tests" / "fixtures" / "sun_reference.json"
PLACES = {
    "berlin": (52.52, 13.405, "Europe/Berlin"), "sydney": (-33.8688, 151.2093, "Australia/Sydney"),
    "new_york": (40.7128, -74.006, "America/New_York"), "tromso": (69.6492, 18.9553, "Europe/Oslo"),
    "quito": (-0.1807, -78.4678, "America/Guayaquil"), "reykjavik": (64.1466, -21.9426, "Atlantic/Reykjavik"),
}
CASES = [
    ("berlin", "2026-11-07"), ("berlin", "2026-06-21"), ("berlin", "2026-12-21"), ("berlin", "2026-03-29"), ("berlin", "2026-10-25"),
    ("sydney", "2026-11-07"), ("sydney", "2026-04-05"), ("sydney", "2026-10-04"), ("new_york", "2026-11-01"), ("new_york", "2026-03-08"),
    ("tromso", "2026-12-15"), ("tromso", "2026-06-21"), ("tromso", "2026-11-07"), ("quito", "2026-11-07"), ("reykjavik", "2026-11-07"),
]


def reference(place: str, day: str) -> dict:
    lat, lon, tz = PLACES[place]
    obs, date, zone = Observer(latitude=lat, longitude=lon), datetime.date.fromisoformat(day), zoneinfo.ZoneInfo(tz)
    row = {"place": place, "date": day, "lat": lat, "lon": lon, "tz": tz}
    try:
        row["rise"] = sunrise(obs, date, tzinfo=zone).astimezone(datetime.UTC).isoformat()
        row["set"] = sunset(obs, date, tzinfo=zone).astimezone(datetime.UTC).isoformat()
    except ValueError:   # the sun does not rise or does not set that day
        noon = datetime.datetime.combine(date, datetime.time(12), zone)
        row["polar"] = "day" if elevation(obs, noon) > 0 else "night"
    return row


def test_fixture_is_astrals_own_result() -> None:
    expected = [reference(place, day) for place, day in CASES]
    stored = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert stored == expected


def test_reference_covers_polar_day_and_night_and_dst_days() -> None:
    rows = {(r["place"], r["date"]): r for r in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    assert rows[("tromso", "2026-12-15")]["polar"] == "night" and rows[("tromso", "2026-06-21")]["polar"] == "day"
    assert all("rise" in rows[k] for k in [("berlin", "2026-03-29"), ("berlin", "2026-10-25"), ("new_york", "2026-11-01"), ("sydney", "2026-04-05")])
