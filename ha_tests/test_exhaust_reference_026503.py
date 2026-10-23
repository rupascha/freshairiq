"""0.26.5.3 (community): the exhaust fan's replacement air comes from the
neighbouring room. Real coordinator runs with Home Assistant states."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.freshairiq.const import (
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY,
    CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE,
)
from ha_tests.test_cov_coordinator_a import START, room, set_climate, set_weather, setup, step

FAN = "switch.bad_luefter"
FLUR_T, FLUR_H = "sensor.flur_t", "sensor.flur_h"
PAIR = {CONF_ROOM_EXHAUST_FAN: [FAN], CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE: FLUR_T, CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY: FLUR_H}


def _flur(hass: HomeAssistant, t: str = "21", h: str = "45") -> None:
    hass.states.async_set(FLUR_T, t, {"unit_of_measurement": "°C"})
    hass.states.async_set(FLUR_H, h, {"unit_of_measurement": "%"})


async def test_windowless_bathroom_uses_the_neighbouring_room(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=95.0)
    set_climate(hass, "bad", 23.0, 80.0)
    _flur(hass)
    hass.states.async_set(FAN, "off")
    _entry, coordinator = await setup(hass, [room("bad", contacts=[], **PAIR)])
    data = await step(hass, freezer, coordinator, 30)
    bad = data["rooms"]["bad"]
    assert (bad["active_reference_temperature_entity"], bad["active_reference_humidity_entity"]) == (FLUR_T, FLUR_H)
    assert bad["data_quality"] == "ok"

    # an unavailable neighbouring sensor never silently becomes outdoor air
    hass.states.async_set(FLUR_H, "unavailable")
    data = await step(hass, freezer, coordinator, 30)
    bad = data["rooms"]["bad"]
    assert bad["active_reference_humidity_entity"] == FLUR_H
    assert bad["data_quality"] != "ok"


async def test_window_room_switches_between_window_and_fan_air(hass: HomeAssistant, freezer) -> None:
    freezer.move_to(START)
    set_weather(hass, temp=2.0, rh=70.0)
    set_climate(hass, "bad", 23.0, 80.0)
    _flur(hass)
    hass.states.async_set(FAN, "off")
    hass.states.async_set("binary_sensor.bad_window", "off")
    _entry, coordinator = await setup(hass, [room("bad", **PAIR)])
    data = await step(hass, freezer, coordinator, 30)
    # fan off, window closed: opening the window is the recommendation -> outdoor air
    assert data["rooms"]["bad"]["active_reference_temperature_entity"] != FLUR_T

    hass.states.async_set(FAN, "on")
    data = await step(hass, freezer, coordinator, 30)
    assert data["rooms"]["bad"]["active_reference_humidity_entity"] == FLUR_H

    hass.states.async_set("binary_sensor.bad_window", "on")
    for _ in range(2):
        data = await step(hass, freezer, coordinator, 5)
    assert data["rooms"]["bad"]["active_reference_humidity_entity"] != FLUR_H


def test_room_form_keeps_the_pair_and_rejects_half_of_it() -> None:
    from custom_components.freshairiq.config_flow_rooms import _normalise_room, _room_section_schema

    base = {"name": "Bad", "temperature": ["sensor.bad_t"], "humidity": ["sensor.bad_h"], "volume": 12.0, "exhaust_fan": [FAN]}
    saved, errors = _normalise_room({**base, **PAIR}, [])
    assert errors == {} and (saved[CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE], saved[CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY]) == (FLUR_T, FLUR_H)
    _saved, errors = _normalise_room({**base, CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE: FLUR_T}, [])
    assert errors == {"base": "exhaust_reference_pair_required"}
    sensors = next(v for k, v in _room_section_schema({}, ["EG"]).schema.items() if str(k) == "sensors")
    assert {CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE, CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY} <= {str(k) for k in sensors.schema.schema}
