"""GitHub #26 (real Home Assistant runtime): after a Home Assistant + FreshAirIQ update every reading was 0 /
unavailable for hours, then came back by itself; no log, no diagnosis (the report has no raw data).

Reproduced here as far as the report allows: FreshAirIQ starts while every source sensor is still unavailable (a
source integration that comes up late after an update). It must show "no data", never invented zeros as values, and
take the real values again as soon as the sources report – without a reload or restart.
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from ha_tests.test_cov_setup_and_platforms import _entry, _room, _setup, _unload

ROOMS = ("wohnzimmer", "bad")


def _sources(hass, state_t: str, state_h: str) -> None:
    hass.states.async_set("sensor.outdoor_temperature", state_t, {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outdoor_humidity", state_h, {"unit_of_measurement": "%"})
    for key in ROOMS:
        hass.states.async_set(f"sensor.{key}_temperature", state_t, {"unit_of_measurement": "°C"})
        hass.states.async_set(f"sensor.{key}_humidity", state_h, {"unit_of_measurement": "%"})
        hass.states.async_set(f"binary_sensor.{key}_window", "off")


async def test_sources_unavailable_at_start_recover_without_reload(hass, freezer) -> None:
    _sources(hass, "unavailable", "unavailable")
    entry = await _setup(hass, _entry(rooms=[_room(k, k.title()) for k in ROOMS]))
    coordinator = entry.runtime_data
    for key in ROOMS:
        room = coordinator.data["rooms"][key]
        assert room.get("data_quality") != "ok"
        # no invented values: an unavailable source is not 0 °C / 0 %
        assert room.get("humidity") in (None, "unavailable") or room.get("data_quality") != "ok"

    # hours later the source integration is back
    freezer.tick(timedelta(hours=3))
    _sources(hass, "21.5", "58")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    for key in ROOMS:
        room = coordinator.data["rooms"][key]
        assert room.get("data_quality") == "ok", key
        assert round(float(room["humidity"])) == 58 and round(float(room["temperature"]), 1) == 21.5
    await _unload(hass, entry)
