"""Future outdoor boundary support for FreshAirIQ.

Uses Home Assistant's configured weather entity only.  Forecasts are optional:
if a provider does not expose hourly temperature/humidity, callers simply fall
back to the current outdoor state and retain the v0.9.6 conservative behaviour.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from math import exp
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .model import absolute_humidity
from .robustness import finite_float


# Upper bound for one weather.get_forecasts action. The call runs inside the
# coordinator update; a hanging weather provider (cloud API, slow add-on) must
# never freeze every FreshAirIQ entity. On timeout the state-attribute fallback
# and the coordinator's cached forecast keep working.
FORECAST_REQUEST_TIMEOUT_SECONDS = 10.0
# 0.26.4.7 (support export with 705 failed fetches in 13 h): a weather entity
# that never delivers hourly temperature + humidity was asked again every
# minute, each time a service call with up to 10 s timeout. Repeated failures
# now back off; one successful fetch resets the schedule.
FORECAST_RETRY_SCHEDULE_SECONDS = (60, 120, 300, 600, 1800, 3600)
FORECAST_REFRESH_SECONDS = 600


def forecast_retry_delay_seconds(consecutive_failures: int) -> int:
    """Seconds until the next hourly-forecast attempt after N failures in a row."""
    index = min(max(int(consecutive_failures), 1), len(FORECAST_RETRY_SCHEDULE_SECONDS)) - 1
    return FORECAST_RETRY_SCHEDULE_SECONDS[index]


def _f(value: Any) -> float | None:
    return finite_float(value)


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dt_util.parse_datetime(str(value))
        if parsed is None:
            return None
        return dt_util.as_local(parsed)
    except (TypeError, ValueError):
        return None


def _rh_from_dewpoint(temp_c: float, dewpoint_c: float) -> float:
    """Magnus approximation, sufficient for forecast boundary reconstruction."""
    a, b = 17.625, 243.04
    sat_t = exp((a * temp_c) / (b + temp_c))
    sat_d = exp((a * dewpoint_c) / (b + dewpoint_c))
    return min(max(100.0 * sat_d / max(sat_t, 1e-9), 0.0), 100.0)


def _extract_rows(payload: Any, entity_id: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if entity_id in payload:
            payload = payload[entity_id]
        if isinstance(payload, dict) and isinstance(payload.get("forecast"), list):
            payload = payload["forecast"]
    if not isinstance(payload, list):
        return []
    return [x for x in payload if isinstance(x, dict)]


async def async_hourly_forecast(
    hass: HomeAssistant, entity_id: str | None, status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return normalised hourly T/RH/AH boundaries from a HA weather entity.

    ``status`` (optional) receives a privacy-safe ``reason`` when nothing usable
    came back: ``timeout``, ``service_error``, ``no_hourly_rows`` or
    ``rows_without_temperature_or_humidity``. Support exports then show *why*
    a weather entity cannot be used instead of only a failure counter.
    """
    if not entity_id:
        return []
    payload: Any = None
    reason: str | None = None
    try:
        async with asyncio.timeout(FORECAST_REQUEST_TIMEOUT_SECONDS):
            payload = await hass.services.async_call(
                "weather", "get_forecasts",
                {"entity_id": entity_id, "type": "hourly"},
                blocking=True, return_response=True,
            )
    except TimeoutError:
        payload, reason = None, "timeout"
    except Exception:  # Provider/HA version may not support action responses.
        payload, reason = None, "service_error"

    rows = _extract_rows(payload, entity_id)
    if not rows:
        state = hass.states.get(entity_id)
        rows = _extract_rows(state.attributes.get("forecast") if state else None, entity_id)
    if not rows and reason is None:
        reason = "no_hourly_rows"

    out: list[dict[str, Any]] = []
    for row in rows:
        when = _dt(row.get("datetime") or row.get("time"))
        temp = _f(row.get("temperature"))
        rh = _f(row.get("humidity"))
        if rh is None:
            dew = _f(row.get("dew_point") if "dew_point" in row else row.get("dewpoint"))
            if temp is not None and dew is not None:
                rh = _rh_from_dewpoint(temp, dew)
        if when is None or temp is None or rh is None or not (-40 <= temp <= 60 and 0 <= rh <= 100):
            continue
        precip = _f(row.get("precipitation"))
        precip_prob = _f(row.get("precipitation_probability"))
        wind_speed = _f(row.get("wind_speed"))
        wind_bearing = _f(row.get("wind_bearing"))
        out.append({
            "datetime": when,
            "temperature_c": round(temp, 2),
            "humidity": round(rh, 1),
            "absolute_humidity": round(absolute_humidity(temp, rh), 3),
            "condition": str(row.get("condition") or ""),
            "precipitation_mm": round(max(precip or 0.0, 0.0), 2),
            "precipitation_probability": round(min(max(precip_prob or 0.0, 0.0), 100.0), 1),
            "wind_speed": round(wind_speed, 2) if wind_speed is not None else None,
            "wind_bearing": round(wind_bearing, 1) if wind_bearing is not None else None,
        })
    out.sort(key=lambda x: x["datetime"])
    if status is not None:
        status["reason"] = None if out else (reason or "rows_without_temperature_or_humidity")
    return out[:48]


def future_boundaries(
    rows: list[dict[str, Any]], now: datetime, current_temp_c: float | None,
    current_rh: float | None, delays: tuple[int, ...] = (15, 30, 60),
) -> dict[int, dict[str, Any]]:
    """Interpolate hourly forecast onto the short Decision Engine horizons."""
    current_temp = finite_float(current_temp_c)
    current_humidity = finite_float(current_rh)
    if (
        current_temp is None or current_humidity is None
        or not (-40 <= current_temp <= 60 and 0 <= current_humidity <= 100)
    ):
        return {}
    current_ah = absolute_humidity(current_temp, current_humidity)
    valid_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("datetime"), datetime):
            continue
        temp = finite_float(row.get("temperature_c"))
        humidity = finite_float(row.get("humidity"))
        if temp is None or humidity is None or not (-40 <= temp <= 60 and 0 <= humidity <= 100):
            continue
        valid_rows.append({**row, "temperature_c": temp, "humidity": humidity})
    points = [{
        "datetime": now,
        "temperature_c": current_temp,
        "humidity": current_humidity,
        "absolute_humidity": current_ah,
    }] + [x for x in valid_rows if x["datetime"] > now]
    if len(points) < 2:
        return {}

    result: dict[int, dict[str, Any]] = {}
    for delay in delays:
        target = now.timestamp() + delay * 60.0
        before = points[0]
        after = None
        for point in points[1:]:
            if point["datetime"].timestamp() >= target:
                after = point
                break
            before = point
        if after is None:
            continue
        t0, t1 = before["datetime"].timestamp(), after["datetime"].timestamp()
        if t1 <= t0 or target - now.timestamp() > 12 * 60 * 60:
            continue
        weight = min(max((target - t0) / (t1 - t0), 0.0), 1.0)
        temp = float(before["temperature_c"]) + (float(after["temperature_c"]) - float(before["temperature_c"])) * weight
        rh = float(before["humidity"]) + (float(after["humidity"]) - float(before["humidity"])) * weight
        ah = absolute_humidity(temp, rh)
        # Confidence represents boundary quality only; Decision Engine combines it
        # with the room-model confidence.
        span_min = (t1 - t0) / 60.0
        confidence = 90 if span_min <= 65 else 78
        result[int(delay)] = {
            "temperature_c": round(temp, 2), "humidity": round(rh, 1),
            "absolute_humidity": round(ah, 3), "confidence": confidence,
            "source": "weather_hourly_interpolated",
        }
    return result
