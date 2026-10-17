"""Sun exposure of openings and the summer shading plan (0.26.5.1).

A window gets direct sun when the sun is above the horizon and its azimuth is
less than 90° away from the direction the window faces. Small margins keep a
cover from flapping when the sun passes the edge of a facade.

The shading plan lists the covers to close in the "summer cooling" profile:
a cover enters a set lead time (default 15 min) before the sun reaches its
window when a warm day is expected (hot forecast, a room above its comfort
target or already warm) and the sky is not densely clouded. It stays in the
list until the sun has left that opening (or the profile changes); a room that
cooled down because of the shading does not open it again. Openings without a
known orientation, or without a sun position, fall back to warmth and
brightness only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import asin, atan2, cos, degrees, radians, sin, tan
from typing import Any

ORIENTATION_DEG = {"n": 0, "ne": 45, "e": 90, "se": 135, "s": 180, "sw": 225, "w": 270, "nw": 315}
SUN_ENTER_ANGLE_DEG = 85.0
SUN_LEAVE_ANGLE_DEG = 95.0
SUN_ENTER_ELEVATION_DEG = 3.0
SUN_LEAVE_ELEVATION_DEG = 0.0
# a shaded cover stays closed until the room is clearly cooler / darker again
# (only used without sun tracking)
SHADE_RELEASE_TEMP_C = 1.0
SHADE_RELEASE_LIGHT_FACTOR = 0.5
DEFAULT_SHADE_LEAD_MIN = 15
DEFAULT_SHADE_FORECAST_MAX_C = 25.0
DEFAULT_SHADE_MAX_CLOUD_COVERAGE = 80.0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def sun_position(attributes: dict[str, Any] | None) -> tuple[float, float] | None:
    """(azimuth, elevation) from the attributes of ``sun.sun``; None when unknown."""
    if not isinstance(attributes, dict):
        return None
    azimuth, elevation = _number(attributes.get("azimuth")), _number(attributes.get("elevation"))
    if azimuth is None or elevation is None:
        return None
    return azimuth % 360.0, elevation


def sun_angle(orientation: str, azimuth: float) -> float | None:
    """Horizontal angle between the window direction and the sun; None = unknown orientation."""
    facing = ORIENTATION_DEG.get(str(orientation).lower())
    if facing is None:
        return None
    return abs((azimuth - facing + 180.0) % 360.0 - 180.0)


def opening_sunlit(orientation: str, sun: tuple[float, float] | None, *, was_sunlit: bool = False) -> bool | None:
    """True/False for direct sun on the opening; None when it cannot be told."""
    if sun is None:
        return None
    angle = sun_angle(orientation, sun[0])
    if angle is None:
        return None
    if was_sunlit:
        return sun[1] > SUN_LEAVE_ELEVATION_DEG and angle < SUN_LEAVE_ANGLE_DEG
    return sun[1] >= SUN_ENTER_ELEVATION_DEG and angle <= SUN_ENTER_ANGLE_DEG


def solar_position(when: datetime, latitude: float, longitude: float) -> tuple[float, float]:
    """(azimuth, elevation) in degrees at ``when`` (aware datetime); accurate to ~0.5°."""
    days = when.astimezone(timezone.utc).timestamp() / 86400.0 + 2440587.5 - 2451545.0
    mean_longitude = (280.460 + 0.9856474 * days) % 360.0
    anomaly = radians((357.528 + 0.9856003 * days) % 360.0)
    ecliptic = radians(mean_longitude + 1.915 * sin(anomaly) + 0.020 * sin(2 * anomaly))
    obliquity = radians(23.439 - 0.0000004 * days)
    right_ascension = atan2(cos(obliquity) * sin(ecliptic), cos(ecliptic))
    declination = asin(sin(obliquity) * sin(ecliptic))
    sidereal = radians(((18.697374558 + 24.06570982441908 * days) % 24.0) * 15.0 + longitude)
    hour_angle = sidereal - right_ascension
    lat = radians(latitude)
    elevation = asin(sin(lat) * sin(declination) + cos(lat) * cos(declination) * cos(hour_angle))
    azimuth = atan2(sin(hour_angle), cos(hour_angle) * sin(lat) - tan(declination) * cos(lat))
    return (degrees(azimuth) + 180.0) % 360.0, degrees(elevation)


def forecast_max_today(rows: Any, now: datetime) -> float | None:
    """Highest forecast temperature for the rest of today (local date of ``now``)."""
    values = []
    for row in rows if isinstance(rows, list) else []:
        when = row.get("datetime") if isinstance(row, dict) else None
        value = _number(row.get("temperature_c")) if isinstance(row, dict) else None
        if isinstance(when, datetime) and value is not None and when.astimezone(now.tzinfo).date() == now.date():
            values.append(value)
    return max(values) if values else None


def shading_plan(
    *,
    cover_openings: list[tuple[str, str]],
    sun: tuple[float, float] | None,
    temperature: float | None,
    illuminance: float | None,
    options: dict[str, Any],
    summer_cooling: bool,
    previous: list[str] | None = None,
    previous_sunlit: list[str] | None = None,
    sun_soon: tuple[float, float] | None = None,
    heat_expected: bool = False,
    cloudy: bool = False,
) -> dict[str, Any]:
    """Covers to close now, plus per-cover sun exposure.

    ``cover_openings`` pairs every cover with the orientation of its opening.
    ``previous`` / ``previous_sunlit`` are the lists of the last cycle.
    ``sun_soon`` is the sun position after the lead time: a cover closes
    before the sun reaches its window. ``heat_expected`` (hot forecast or a
    room above its comfort target) replaces "the room is already warm";
    ``cloudy`` (dense cloud cover) keeps open covers open.
    """
    held = set(previous or [])
    lit_before = set(previous_sunlit or [])
    threshold_temp = float(options.get("shade_above_temp_c", 24.0))
    threshold_light = float(options.get("shade_min_illuminance_lx", 10000.0))
    hot = temperature is not None and temperature >= threshold_temp
    still_warm = temperature is not None and temperature >= threshold_temp - SHADE_RELEASE_TEMP_C
    bright = illuminance is None or illuminance >= threshold_light
    still_bright = illuminance is None or illuminance >= threshold_light * SHADE_RELEASE_LIGHT_FACTOR
    covers: list[str] = []
    sunlit: list[str] = []
    soon: list[str] = []
    not_sunlit: list[str] = []
    for cover, orientation in cover_openings:
        lit = opening_sunlit(orientation, sun, was_sunlit=cover in lit_before)
        lit_soon = opening_sunlit(orientation, sun_soon) is True
        if lit is True:
            sunlit.append(cover)
        elif lit_soon:
            soon.append(cover)
        elif lit is False:
            not_sunlit.append(cover)
        if not summer_cooling or cover in covers:
            continue
        if lit is None:
            # no orientation or no sun position: warmth and brightness decide
            keep = (still_warm and still_bright) if cover in held else (hot and bright)
        elif cover in held:
            keep = lit is True or lit_soon
        else:
            # a sunlit window measured dark means clouds; before the sun arrives
            # the indoor light level tells nothing
            dark = lit is True and not bright
            keep = (hot or heat_expected) and not cloudy and not dark and (lit is True or lit_soon)
        if keep:
            covers.append(cover)
    return {
        "covers_to_close": covers,
        "sunlit_covers": sunlit,
        "sun_soon_covers": soon,
        "shaded_side_covers": not_sunlit,
        "sun_tracking": sun is not None,
    }
