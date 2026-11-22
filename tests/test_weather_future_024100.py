from __future__ import annotations

from datetime import datetime, timezone
import importlib
import sys
import types

import pytest


def _load_module():
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    sys.modules["homeassistant"] = sys.modules.get("homeassistant", types.ModuleType("homeassistant"))
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.util"] = sys.modules.get("homeassistant.util", types.ModuleType("homeassistant.util"))
    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.parse_datetime = lambda value: datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    dt_mod.as_local = lambda value: value
    sys.modules["homeassistant.util.dt"] = dt_mod
    sys.modules["homeassistant.util"].dt = dt_mod
    sys.modules.pop("custom_components.freshairiq.weather_future", None)
    return importlib.import_module("custom_components.freshairiq.weather_future")


class _Services:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    async def async_call(self, domain, service, data, *, blocking, return_response):
        self.calls.append((domain, service, data, blocking, return_response))
        if self.error:
            raise self.error
        return self.payload


class _State:
    def __init__(self, attributes):
        self.attributes = attributes


class _States:
    def __init__(self, state=None):
        self.state = state

    def get(self, entity_id):
        return self.state


class _Hass:
    def __init__(self, payload=None, state=None, error=None):
        self.services = _Services(payload, error)
        self.states = _States(state)


@pytest.mark.asyncio
async def test_hourly_forecast_normalises_action_response_and_dewpoint():
    wf = _load_module()
    payload = {
        "weather.home": {
            "forecast": [
                {"datetime": "2026-09-14T09:00:00+00:00", "temperature": 20, "humidity": 50, "precipitation": -2, "precipitation_probability": 120, "wind_speed": 4.2, "wind_bearing": 270},
                {"datetime": "2026-09-14T10:00:00+00:00", "temperature": 18, "dew_point": 10},
                {"datetime": "bad", "temperature": 999, "humidity": 50},
            ]
        }
    }
    hass = _Hass(payload=payload)
    rows = await wf.async_hourly_forecast(hass, "weather.home")
    assert len(rows) == 2
    assert rows[0]["temperature_c"] == 20.0
    assert rows[0]["precipitation_mm"] == 0.0
    assert rows[0]["precipitation_probability"] == 100.0
    assert 0 < rows[1]["humidity"] < 100
    assert rows[1]["absolute_humidity"] > 0
    assert hass.services.calls[0][0:2] == ("weather", "get_forecasts")


@pytest.mark.asyncio
async def test_hourly_forecast_falls_back_to_state_attributes_when_action_fails():
    wf = _load_module()
    state = _State({"forecast": [{"datetime": "2026-09-14T09:00:00+00:00", "temperature": 12, "humidity": 80}]})
    rows = await wf.async_hourly_forecast(_Hass(state=state, error=RuntimeError("unsupported")), "weather.home")
    assert len(rows) == 1
    assert rows[0]["humidity"] == 80.0
    assert await wf.async_hourly_forecast(_Hass(), None) == []


def test_extract_rows_accepts_supported_payload_shapes_only():
    wf = _load_module()
    row = {"temperature": 10}
    assert wf._extract_rows({"weather.home": {"forecast": [row]}}, "weather.home") == [row]
    assert wf._extract_rows({"forecast": [row, "bad"]}, "weather.home") == [row]
    assert wf._extract_rows("bad", "weather.home") == []


def test_future_boundaries_interpolates_and_rejects_invalid_inputs():
    wf = _load_module()
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    rows = [
        {"datetime": datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc), "temperature_c": 10.0, "humidity": 80.0},
        {"datetime": datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc), "temperature_c": 8.0, "humidity": 85.0},
        {"datetime": "invalid", "temperature_c": 5, "humidity": 90},
    ]
    out = wf.future_boundaries(rows, now, 20.0, 50.0, delays=(30, 60, 90))
    assert set(out) == {30, 60, 90}
    assert out[30]["temperature_c"] == 15.0
    assert out[60]["temperature_c"] == 10.0
    assert out[90]["temperature_c"] == 9.0
    assert out[30]["confidence"] == 90
    assert wf.future_boundaries(rows, now, None, 50.0) == {}
    assert wf.future_boundaries([], now, 20.0, 50.0) == {}


def test_rh_from_dewpoint_is_bounded():
    wf = _load_module()
    assert 0 <= wf._rh_from_dewpoint(20, 10) <= 100
    assert wf._rh_from_dewpoint(10, 20) == 100.0


# 0.26.7.2 (support diagnosis 21.11.): the hourly rows by their absolute time. On 25.10.2026 at 02:30 summer time (00:30 UTC)
# the hour 02:00 winter time (01:00 UTC) still lies 30 minutes ahead – compared by the local wall clock it looked past.
BERLIN = __import__("zoneinfo").ZoneInfo("Europe/Berlin")
DST_ROWS = [
    {"datetime": "2026-10-25T02:00:00+00:00", "temperature": 12, "humidity": 70},   # 03:00 winter time
    {"datetime": "2026-10-25T01:00:00+00:00", "temperature": 8, "humidity": 80},    # 02:00 winter time
    {"datetime": "2026-10-25T00:00:00+00:00", "temperature": 7, "humidity": 82},    # 02:00 summer time
    {"datetime": "2026-10-24T23:00:00+00:00", "temperature": 7, "humidity": 82},    # 01:00 summer time
]


def _local(wf):
    wf.dt_util.as_local = lambda value: value.astimezone(BERLIN)
    return wf


@pytest.mark.asyncio
async def test_hourly_rows_are_ordered_by_absolute_time_across_the_dst_change():
    wf = _local(_load_module())
    rows = await wf.async_hourly_forecast(_Hass(payload={"weather.home": {"forecast": DST_ROWS}}), "weather.home")
    assert [row["datetime"].astimezone(timezone.utc).hour for row in rows] == [23, 0, 1, 2]
    now = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc).astimezone(BERLIN)   # 02:30 summer time
    assert (now.hour, now.minute, now.fold, rows[2]["datetime"].hour, rows[2]["datetime"].fold) == (2, 30, 0, 2, 1)
    out = wf.future_boundaries(rows, now, 6.0, 85.0, delays=(30, 60, 90))
    assert out[30]["temperature_c"] == 8.0                                           # 02:00 winter time, 30 min ahead
    assert out[90]["temperature_c"] == 12.0
    assert out[30]["confidence"] == 90


def test_future_boundaries_filter_by_absolute_time_in_one_zone():
    wf = _load_module()
    now = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc).astimezone(BERLIN)
    winter_two = datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc).astimezone(BERLIN)
    summer_two = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc).astimezone(BERLIN)
    rows = [{"datetime": winter_two, "temperature_c": 8.0, "humidity": 80.0},
            {"datetime": summer_two, "temperature_c": 30.0, "humidity": 20.0}]          # past: never used
    assert wf.future_boundaries(rows, now, 6.0, 85.0, delays=(30,))[30]["temperature_c"] == 8.0


@pytest.mark.parametrize(("unit", "value", "expected"), [
    ("in", 0.1, 2.54),
    ("cm", 0.3, 3.0),
    ("mm", 1.7, 1.7),
    (None, 1.7, 1.7),        # older weather entities without a unit: as before
])
@pytest.mark.asyncio
async def test_forecast_precipitation_follows_the_entity_unit(unit, value, expected):
    wf = _load_module()
    attributes = {"temperature_unit": "°C", **({"precipitation_unit": unit} if unit else {})}
    payload = {"weather.home": {"forecast": [{"datetime": "2026-11-21T09:00:00+00:00", "temperature": 5, "humidity": 90, "precipitation": value}]}}
    rows = await wf.async_hourly_forecast(_Hass(payload=payload, state=_State(attributes)), "weather.home")
    assert rows[0]["precipitation_mm"] == expected
