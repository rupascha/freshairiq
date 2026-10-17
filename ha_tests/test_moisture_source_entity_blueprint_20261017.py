"""0.26.5.1 (community: run the bathroom fan only after showering).

* ``binary_sensor.<room>_moisture_source`` is on while FreshAirIQ detects an
  internal moisture source; enabled by default for rooms with configured sources.
* The real blueprint "fan after moisture source" (DE/EN) switches a device on at
  the start, off after the follow-up time, at the maximum runtime at the latest,
  and also after a restart of Home Assistant.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.freshairiq.const import CONF_ROOM_MOISTURE_SOURCES, DOMAIN
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints" / "automation" / "freshairiq"
SENSOR = "binary_sensor.bad_feuchtequelle"
FAN = "input_boolean.bad_luefter"


# --------------------------------------------------------------------------- entity
def _source_entity(hass, room_key: str):
    registry = er.async_get(hass)
    return next(e for e in registry.entities.values()
                if e.platform == DOMAIN and e.unique_id.endswith(f"{room_key}_moisture_source"))


async def test_moisture_source_entity_follows_the_detector(hass) -> None:
    bad = {**_room("bad", "Bad"), CONF_ROOM_MOISTURE_SOURCES: ["shower"]}
    _set_sources(hass, "bad", "wohnzimmer")
    entry = await _setup(hass, _entry(rooms=[bad, _room()]))
    bad_entity = _source_entity(hass, "bad")
    assert bad_entity.disabled_by is None
    living = _source_entity(hass, "wohnzimmer")
    assert living.disabled_by is er.RegistryEntryDisabler.INTEGRATION  # no source configured: available, off by default
    state = hass.states.get(bad_entity.entity_id)
    assert state.state == "off" and state.attributes["source"] is None and state.attributes["recovery"] is False

    coordinator = entry.runtime_data
    coordinator.data["rooms"]["bad"].update({
        "moisture_source_active": True, "moisture_source_identified_source": "shower", "moisture_source_confidence": 86,
        "moisture_source_rate_ml_min": 9.1, "moisture_source_generated_ml_window": 52.0,
        "moisture_source_started_at": "2026-10-17T07:02:00+02:00",
    })
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(bad_entity.entity_id)
    assert state.state == "on"
    assert {k: state.attributes[k] for k in ("source", "confidence", "rate_ml_min", "generated_ml", "started_at")} == {
        "source": "shower", "confidence": 86, "rate_ml_min": 9.1, "generated_ml": 52.0, "started_at": "2026-10-17T07:02:00+02:00"}
    await _unload(hass, entry)


# --------------------------------------------------------------------------- blueprint
@pytest.fixture
async def fan(hass, tmp_path, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 17, 7, 0, tzinfo=ZoneInfo("Europe/Berlin")))
    hass.config.config_dir = str(tmp_path)
    target = tmp_path / "blueprints" / "automation" / "freshairiq"
    target.mkdir(parents=True)
    for path in SOURCE.glob("*.yaml"):
        shutil.copy(path, target / path.name)
    await _set(hass, "off", None)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"bad_luefter": {}}})
    yield freezer
    # stop runs that still wait for the follow-up (time is frozen in these tests)
    for state in hass.states.async_all("automation"):
        await hass.services.async_call("automation", "turn_off", {"entity_id": state.entity_id, "stop_actions": True}, blocking=True)


async def _automation(hass, file="fan_after_moisture_source.yaml", **inputs) -> None:
    values = {"moisture_source": SENSOR, "device": FAN, **inputs}
    assert await async_setup_component(hass, "automation", {"automation": [
        {"id": "fan_after_source", "use_blueprint": {"path": f"freshairiq/{file}", "input": values}},
    ]})
    await hass.async_block_till_done()


async def _settle() -> None:
    # Automation runs that wait for the follow-up stay pending on purpose, so
    # hass.async_block_till_done() would wait for them; just let the loop run.
    for _ in range(20):
        await asyncio.sleep(0)


async def _set(hass, state: str, source=None) -> None:
    hass.states.async_set(SENSOR, state, {"source": source})
    await _settle()


async def _advance(hass, freezer, minutes: float) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await _settle()


def _fan(hass) -> str:
    return hass.states.get(FAN).state


@pytest.mark.parametrize("file", ["fan_after_moisture_source.yaml", "fan_after_moisture_source_en.yaml"])
async def test_shower_switches_the_fan_on_and_off_after_the_follow_up(hass, fan, file) -> None:
    await _automation(hass, file)
    await _set(hass, "on", "shower")
    assert _fan(hass) == "on"
    await _advance(hass, fan, 12)
    assert _fan(hass) == "on"  # still showering
    await _set(hass, "off", None)
    await _advance(hass, fan, 9)
    assert _fan(hass) == "on"  # default follow-up: 10 min
    await _advance(hass, fan, 2)
    assert _fan(hass) == "off"


async def test_source_filter_and_unspecified_sources(hass, fan) -> None:
    await _automation(hass, sources=["shower"])
    await _set(hass, "on", "cooking")
    assert _fan(hass) == "off"
    await _set(hass, "off", None)
    hass.states.async_set(SENSOR, "on", {"source": None})  # not identified
    await hass.async_block_till_done()
    assert _fan(hass) == "off"
    await _set(hass, "off", None)
    await _set(hass, "on", "shower")
    assert _fan(hass) == "on"


async def test_unspecified_source_can_be_selected(hass, fan) -> None:
    await _automation(hass, sources=["unknown"])
    await _set(hass, "on", None)
    assert _fan(hass) == "on"


async def test_maximum_runtime_and_short_follow_up(hass, fan) -> None:
    await _automation(hass, follow_up=2, max_runtime=30)
    await _set(hass, "on", "shower")
    await _advance(hass, fan, 29)
    assert _fan(hass) == "on"
    await _advance(hass, fan, 2)
    assert _fan(hass) == "off"  # source still on, but the maximum runtime is reached


async def test_device_left_on_after_a_restart_is_switched_off(hass, fan) -> None:
    # Home Assistant restarted while the fan ran: the source is already "on" when the
    # automation loads, so no run waits for the follow-up – the stop trigger still ends it.
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": FAN}, blocking=True)
    hass.states.async_set(SENSOR, "on", {"source": "shower"})
    await _automation(hass, follow_up=5)
    assert _fan(hass) == "on"
    await _set(hass, "off", None)
    await _advance(hass, fan, 4)
    assert _fan(hass) == "on"
    await _advance(hass, fan, 2)
    assert _fan(hass) == "off"
