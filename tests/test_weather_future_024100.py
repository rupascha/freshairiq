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
