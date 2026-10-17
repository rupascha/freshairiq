"""0.26.5.1 (community feedback): sun protection by window orientation and sun position.

In the "summer cooling" profile a cover is to be closed when the room is warm,
it is bright and the sun shines on its opening. It is released once the sun
has left that opening - not when the room cooled down thanks to the shading.
"""
from __future__ import annotations

from custom_components.freshairiq.intervention import build_interventions
from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.sun_exposure import (
    forecast_max_today,
    opening_sunlit,
    shading_plan,
    solar_position,
    sun_angle,
    sun_position,
)

OPTIONS = {"shade_above_temp_c": 24.0, "shade_min_illuminance_lx": 10000.0}
MORNING = (100.0, 30.0)   # east-south-east
NOON = (180.0, 60.0)
EVENING = (275.0, 10.0)   # west
NIGHT = (350.0, -15.0)


def _plan(covers, sun, *, temperature=27.0, illuminance=None, summer=True, previous=None, sunlit=None, **extra):
    return shading_plan(
        cover_openings=covers, sun=sun, temperature=temperature, illuminance=illuminance,
        options=OPTIONS, summer_cooling=summer, previous=previous, previous_sunlit=sunlit, **extra,
    )


def test_sun_position_reads_sun_sun_attributes() -> None:
    assert sun_position({"azimuth": 370.5, "elevation": "12.5"}) == (10.5, 12.5)
    assert sun_position({"azimuth": None, "elevation": 3}) is None
    assert sun_position({"azimuth": "x", "elevation": 3}) is None
    assert sun_position({"azimuth": float("nan"), "elevation": 3}) is None
    assert sun_position(None) is None


def test_sun_angle_and_sunlit_with_margins() -> None:
    assert sun_angle("S", 180.0) == 0.0
    assert sun_angle("n", 350.0) == 10.0
    assert sun_angle("unknown", 180.0) is None
    assert opening_sunlit("e", MORNING) is True
    assert opening_sunlit("w", MORNING) is False
    assert opening_sunlit("s", NIGHT) is False
    assert opening_sunlit("s", None) is None
    assert opening_sunlit("unknown", NOON) is None
    # 90° away: not yet sunlit when entering, but still sunlit while leaving
    assert opening_sunlit("e", (180.0, 40.0)) is False
    assert opening_sunlit("e", (180.0, 40.0), was_sunlit=True) is True
    assert opening_sunlit("e", (190.0, 40.0), was_sunlit=True) is False
    # low sun: enters from 3°, leaves below the horizon
    assert opening_sunlit("w", (270.0, 1.0)) is False
    assert opening_sunlit("w", (270.0, 1.0), was_sunlit=True) is True


def test_only_sunlit_covers_close_in_summer_cooling() -> None:
    covers = [("cover.east", "e"), ("cover.west", "w"), ("cover.roof", "unknown")]
    morning = _plan(covers, MORNING)
    assert morning["covers_to_close"] == ["cover.east", "cover.roof"]
    assert morning["sunlit_covers"] == ["cover.east"]
    assert morning["shaded_side_covers"] == ["cover.west"]
    assert morning["sun_tracking"] is True
    # other profiles: exposure is reported, nothing to close
    other = _plan(covers, MORNING, summer=False)
    assert other["covers_to_close"] == [] and other["sunlit_covers"] == ["cover.east"]
    # cool or dark room: nothing new is closed
    assert _plan(covers, MORNING, temperature=23.0)["covers_to_close"] == []
    assert _plan(covers, MORNING, temperature=None)["covers_to_close"] == []
    assert _plan(covers, MORNING, illuminance=5000.0)["covers_to_close"] == []


def test_a_shaded_cover_stays_closed_until_the_sun_has_left() -> None:
    covers = [("cover.east", "e"), ("cover.west", "w")]
    first = _plan(covers, MORNING)
    # room cooled down thanks to the shading: the cover stays closed
    cooled = _plan(covers, MORNING, temperature=22.0, previous=first["covers_to_close"], sunlit=first["sunlit_covers"])
    assert cooled["covers_to_close"] == ["cover.east"]
    # the sun moved to the west: east opens, west closes
    afternoon = _plan(covers, EVENING, previous=cooled["covers_to_close"], sunlit=cooled["sunlit_covers"])
    assert afternoon["covers_to_close"] == ["cover.west"]
    # sunset releases the west cover too
    night = _plan(covers, NIGHT, previous=afternoon["covers_to_close"], sunlit=afternoon["sunlit_covers"])
    assert night["covers_to_close"] == []


def test_without_sun_tracking_warmth_and_light_decide_with_hysteresis() -> None:
    covers = [("cover.a", "s"), ("cover.a", "s")]
    first = _plan(covers, None, illuminance=20000.0)
    assert first["covers_to_close"] == ["cover.a"] and first["sun_tracking"] is False
    held = _plan(covers, None, temperature=23.2, illuminance=6000.0, previous=["cover.a"])
    assert held["covers_to_close"] == ["cover.a"]
    assert _plan(covers, None, temperature=22.9, illuminance=20000.0, previous=["cover.a"])["covers_to_close"] == []
    assert _plan(covers, None, temperature=26.0, illuminance=4000.0, previous=["cover.a"])["covers_to_close"] == []
    # leaving the profile releases everything
    assert _plan(covers, None, summer=False, previous=["cover.a"])["covers_to_close"] == []


def test_shade_intervention_skips_openings_without_sun() -> None:
    config = {"contact_covers": {"binary_sensor.east": ["cover.east"], "binary_sensor.west": ["cover.west"]}}
    room = {"temperature": 27.0, "humidity": 50.0, "shading": {"shaded_side_covers": ["cover.west"]}}
    shade = [i["entity_id"] for i in build_interventions(room=room, config=config, options=OPTIONS) if i["key"] == "shade"]
    assert shade == ["cover.east"]
    room.pop("shading")
    shade = [i["entity_id"] for i in build_interventions(room=room, config=config, options=OPTIONS) if i["key"] == "shade"]
    assert sorted(shade) == ["cover.east", "cover.west"]


# --------------------------------------------------------------------------- lead time, heat, clouds
BERLIN = (52.52, 13.405)


def test_solar_position_matches_reference_values() -> None:
    # reference: astral (NOAA), Berlin
    azimuth, elevation = solar_position(datetime(2026, 7, 15, 11, 20, tzinfo=timezone.utc), *BERLIN)
    assert abs(azimuth - 183.43) < 0.1 and abs(elevation - 58.92) < 0.1
    azimuth, elevation = solar_position(datetime(2026, 6, 21, 5, 0, tzinfo=timezone.utc), *BERLIN)
    assert abs(azimuth - 73.71) < 0.1 and abs(elevation - 17.21) < 0.1


def test_forecast_max_today_only_counts_today() -> None:
    now = datetime(2026, 7, 15, 9, 0, tzinfo=timezone(timedelta(hours=2)))
    rows = [
        {"datetime": now + timedelta(hours=4), "temperature_c": 29.5},
        {"datetime": now + timedelta(hours=20), "temperature_c": 33.0},  # tomorrow
        {"datetime": "x", "temperature_c": 40.0},
        {"datetime": now, "temperature_c": None},
        "bad",
    ]
    assert forecast_max_today(rows, now) == 29.5
    assert forecast_max_today([], now) is None
    assert forecast_max_today(None, now) is None


def test_covers_close_ahead_of_the_sun_on_a_warm_day() -> None:
    covers = [("cover.east", "e"), ("cover.west", "w")]
    before_sunrise_on_east = (60.0, 2.0)
    soon = (80.0, 8.0)
    # room still cool, but a hot day is expected: the east cover closes before the sun arrives
    plan = _plan(covers, before_sunrise_on_east, temperature=21.0, sun_soon=soon, heat_expected=True)
    assert plan["covers_to_close"] == ["cover.east"]
    assert plan["sun_soon_covers"] == ["cover.east"] and plan["shaded_side_covers"] == ["cover.west"]
    # a cool day: nothing closes
    assert _plan(covers, before_sunrise_on_east, temperature=21.0, sun_soon=soon)["covers_to_close"] == []
    # indoor light before the sun arrives does not block closing ahead
    assert _plan(covers, before_sunrise_on_east, temperature=21.0, illuminance=50.0, sun_soon=soon,
                 heat_expected=True)["covers_to_close"] == ["cover.east"]
    # the closed cover stays closed while the sun is still to come
    held = _plan(covers, before_sunrise_on_east, temperature=21.0, sun_soon=soon, previous=["cover.east"])
    assert held["covers_to_close"] == ["cover.east"]


def test_clouds_keep_open_covers_open_but_not_closed_ones() -> None:
    covers = [("cover.east", "e")]
    assert _plan(covers, MORNING, cloudy=True)["covers_to_close"] == []
    assert _plan(covers, MORNING, cloudy=True, previous=["cover.east"], sunlit=["cover.east"])["covers_to_close"] == ["cover.east"]
