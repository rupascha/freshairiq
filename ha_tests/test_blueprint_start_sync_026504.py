"""0.26.5.4 (audit S07): device blueprints bring the device in line after a restart.

FreshAirIQ fires its events only on changes, and the first cycle after a start is
silent on purpose (no replayed announcements). A device blueprint therefore never
heard of a recommendation that already held when Home Assistant started: the fan
stayed off (or on) until the recommendation changed. The real blueprints are
loaded into real automations; the announce blueprint stays silent at a start.
"""
from __future__ import annotations

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from ha_tests.test_blueprint_basis_20261017 import ROOM_SENSOR, _announce_automation, _device_automation, blueprints  # noqa: F401
from ha_tests.test_moisture_source_entity_blueprint_20261017 import (  # noqa: F401
    FAN, SENSOR, _automation, _fan, _set, _settle, fan,
)

DEVICE = "input_boolean.bad_luefter"


def _room_state(hass, action: str, aligned: str, *, active: bool = False) -> None:
    hass.states.async_set(ROOM_SENSOR, action, {"freshairiq_room_key": "bad",
                                                "freshairiq_room_payload": {"house_aligned_action": aligned, "active": active}})


async def _start(hass) -> None:
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.parametrize("file", ["device_follows_room_action.yaml", "device_follows_room_action_en.yaml"])
async def test_a_recommendation_holding_at_the_start_switches_the_device_on(hass, blueprints, file) -> None:
    _room_state(hass, "ventilate", "ventilate")
    await _device_automation(hass, file, None)
    assert hass.states.get(DEVICE).state == "off"
    await _start(hass)
    assert hass.states.get(DEVICE).state == "on"


async def test_the_start_sync_follows_the_chosen_basis_and_the_open_window(hass, blueprints) -> None:
    _room_state(hass, "ventilate", "close")  # the room alone would air, the house says close
    await _device_automation(hass, "device_follows_room_action.yaml", "house")
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": DEVICE}, blocking=True)
    await _start(hass)
    assert hass.states.get(DEVICE).state == "off"  # a device left running is switched off


async def test_the_start_sync_waits_for_freshairiq(hass, blueprints) -> None:
    hass.states.async_set(ROOM_SENSOR, "unavailable", {"freshairiq_room_key": "bad"})
    await _device_automation(hass, "device_follows_room_action.yaml", "room")
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    assert hass.states.get(DEVICE).state == "off"
    _room_state(hass, "ventilate", "ventilate", active=True)  # window open: not switched on
    await hass.async_block_till_done()
    assert hass.states.get(DEVICE).state == "off"


async def test_the_announce_blueprint_stays_silent_at_a_start(hass, blueprints) -> None:
    _room_state(hass, "close", "close")
    calls = await _announce_automation(hass, "announce_room_action.yaml", None)
    await _start(hass)
    assert calls == []


@pytest.mark.parametrize("file", ["fan_after_moisture_source.yaml", "fan_after_moisture_source_en.yaml"])
async def test_a_moisture_source_running_at_the_start_switches_the_fan_on(hass, fan, file) -> None:
    await _set(hass, "on", "shower")
    await _automation(hass, file)
    assert _fan(hass) == "off"
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    assert _fan(hass) == "on"


async def test_no_start_without_a_running_source(hass, fan) -> None:
    await _automation(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    assert _fan(hass) == "off"


# --------------------------------------------------------------------------- audit of the 0.26.5.4(4) artefact

async def test_n05_the_start_sync_waits_for_a_room_sensor_that_does_not_exist_yet(hass, blueprints) -> None:
    hass.states.async_remove(ROOM_SENSOR)
    await _device_automation(hass, "device_follows_room_action.yaml", "room")
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    assert hass.states.get(DEVICE).state == "off"
    hass.states.async_set(ROOM_SENSOR, "unavailable", {})  # created, but no FreshAirIQ result yet
    await _settle()
    assert hass.states.get(DEVICE).state == "off"
    _room_state(hass, "ventilate", "ventilate")
    await hass.async_block_till_done()
    assert hass.states.get(DEVICE).state == "on"


async def test_reloading_automations_syncs_the_device_as_well(hass, blueprints) -> None:
    _room_state(hass, "ventilate", "ventilate")
    await _device_automation(hass, "device_follows_room_action_en.yaml", None)
    hass.bus.async_fire("automation_reloaded")
    await hass.async_block_till_done()
    assert hass.states.get(DEVICE).state == "on"


def _ended(hass, minutes_ago: float, state: str = "off", source=None) -> None:
    from homeassistant.util import dt as dt_util

    ended = (dt_util.now() - __import__("datetime").timedelta(minutes=minutes_ago)).isoformat()
    hass.states.async_set(SENSOR, state, {"source": source, "last_ended_at": ended})


@pytest.mark.parametrize("file", ["fan_after_moisture_source.yaml", "fan_after_moisture_source_en.yaml"])
async def test_n03_a_restart_during_the_follow_up_still_switches_the_fan_off(hass, fan, file) -> None:
    from ha_tests.test_moisture_source_entity_blueprint_20261017 import _advance

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": FAN}, blocking=True)  # left running
    _ended(hass, 4)  # the shower ended 4 minutes before the restart: 6 of 10 follow-up minutes are left
    await _automation(hass, file)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    assert _fan(hass) == "on"
    await _advance(hass, fan, 5)
    assert _fan(hass) == "on"
    await _advance(hass, fan, 2)
    assert _fan(hass) == "off"


async def test_f03_a_fan_switched_on_by_hand_is_left_alone_after_a_restart(hass, fan) -> None:
    from ha_tests.test_moisture_source_entity_blueprint_20261017 import _advance

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": FAN}, blocking=True)
    await _automation(hass)
    for case in (lambda: _ended(hass, 180), lambda: hass.states.async_set(SENSOR, "off", {"source": None, "last_ended_at": None}),
                 lambda: _ended(hass, 3, state="unavailable"), lambda: _ended(hass, 3, state="unknown")):
        case()  # source ended long ago / never / sensor without a valid state
        hass.bus.async_fire("automation_reloaded")
        await _settle()
        await _advance(hass, fan, 15)
        assert _fan(hass) == "on"


async def test_f03_with_a_source_filter_an_unknown_ended_source_is_left_alone(hass, fan) -> None:
    from ha_tests.test_moisture_source_entity_blueprint_20261017 import _advance

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": FAN}, blocking=True)
    await _automation(hass, sources=["shower"])
    _ended(hass, 2)  # after a restart FreshAirIQ no longer knows which source it was
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    await _advance(hass, fan, 15)
    assert _fan(hass) == "on"
    _ended(hass, 2, source="shower")
    hass.bus.async_fire("automation_reloaded")
    await _settle()
    await _advance(hass, fan, 9)
    assert _fan(hass) == "off"


async def test_n03_a_new_source_during_the_remaining_follow_up_keeps_the_fan_running(hass, fan) -> None:
    from ha_tests.test_moisture_source_entity_blueprint_20261017 import _advance

    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": FAN}, blocking=True)
    _ended(hass, 1)
    await _automation(hass)
    hass.bus.async_fire("automation_reloaded")
    await _settle()
    await _advance(hass, fan, 3)
    await _set(hass, "on", "shower")  # restarts the automation: the fan follows the new source
    await _advance(hass, fan, 15)
    assert _fan(hass) == "on"


async def test_n03_nothing_happens_at_a_start_when_the_fan_is_off(hass, fan) -> None:
    from ha_tests.test_moisture_source_entity_blueprint_20261017 import _advance

    await _automation(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await _settle()
    await _advance(hass, fan, 15)
    assert _fan(hass) == "off"
