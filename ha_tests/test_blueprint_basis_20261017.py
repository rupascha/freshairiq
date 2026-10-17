"""Blueprints let the user choose the basis: house decision or room only (feedback FAIQ-FB-EE8489B6176D).

The announce blueprint used the raw room action, so it said "close" while the card
(house decision) still showed "keep airing". Both blueprints now offer the basis;
the real blueprints are loaded into real automations here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest

from homeassistant.setup import async_setup_component

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints" / "automation" / "freshairiq"
ROOM_SENSOR = "sensor.bad_aktion"


@pytest.fixture
async def blueprints(hass, tmp_path, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 17, 12, 0, tzinfo=ZoneInfo("Europe/Berlin")))  # outside quiet time
    hass.config.config_dir = str(tmp_path)
    target = tmp_path / "blueprints" / "automation" / "freshairiq"
    target.mkdir(parents=True)
    for path in SOURCE.glob("*.yaml"):
        shutil.copy(path, target / path.name)
    hass.states.async_set(ROOM_SENSOR, "okay", {"freshairiq_room_key": "bad"})
    yield


def _room_action(action: str, aligned: str) -> dict:
    return {"room_key": "bad", "room_name": "Bad", "action": action, "house_aligned_action": aligned,
            "message": f"Bad: raw {action}.", "ventilation_active": False}


def _recommendation(code: str, previous: str) -> dict:
    return {"room_key": "bad", "room_name": "Bad", "action": "close", "recommendation": code,
            "previous_recommendation": previous, "message": f"Bad: house {code}.", "ventilation_active": False}


async def _announce_automation(hass, file: str, basis: str | None) -> list:
    calls: list = []
    hass.bus.async_listen("test_announce", lambda event: calls.append(event.data["msg"]))
    inputs = {"rooms": [ROOM_SENSOR], "actions_filter": ["close", "continue_ventilating"],
              "output": [{"event": "test_announce", "event_data": {"msg": "{{ message }}"}}]}
    if basis is not None:
        inputs["basis"] = basis
    assert await async_setup_component(hass, "automation", {"automation": [
        {"id": f"announce_{basis}", "use_blueprint": {"path": f"freshairiq/{file}", "input": inputs}},
    ]})
    await hass.async_block_till_done()
    return calls


@pytest.mark.parametrize("file", ["announce_room_action.yaml", "announce_room_action_en.yaml"])
async def test_announce_defaults_to_the_house_decision(hass, blueprints, file) -> None:
    calls = await _announce_automation(hass, file, None)
    # room alone would close, the house keeps airing: no premature "close"
    hass.bus.async_fire("freshairiq_room_action", _room_action("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert calls == []
    hass.bus.async_fire("freshairiq_room_recommendation", _recommendation("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert calls == ["Bad: house close."]


async def test_announce_room_only_follows_the_raw_room_action(hass, blueprints) -> None:
    calls = await _announce_automation(hass, "announce_room_action.yaml", "room")
    hass.bus.async_fire("freshairiq_room_recommendation", _recommendation("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert calls == []
    hass.bus.async_fire("freshairiq_room_action", _room_action("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert calls == ["Bad: raw close."]


async def _device_automation(hass, file: str, basis: str | None) -> None:
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"bad_luefter": {}}})
    inputs = {"room": ROOM_SENSOR, "device": "input_boolean.bad_luefter",
              "on_actions": ["ventilate", "continue_ventilating"], "only_when_windows_closed": True}
    if basis is not None:
        inputs["basis"] = basis
    assert await async_setup_component(hass, "automation", {"automation": [
        {"id": f"device_{basis}", "use_blueprint": {"path": f"freshairiq/{file}", "input": inputs}},
    ]})
    await hass.async_block_till_done()


@pytest.mark.parametrize("file", ["device_follows_room_action.yaml", "device_follows_room_action_en.yaml"])
async def test_device_defaults_to_room_only_unchanged(hass, blueprints, file) -> None:
    await _device_automation(hass, file, None)
    hass.bus.async_fire("freshairiq_room_recommendation", _recommendation("continue_ventilating", "ventilate"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "off"
    hass.bus.async_fire("freshairiq_room_action", _room_action("ventilate", "ventilate"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "on"
    hass.bus.async_fire("freshairiq_room_action", _room_action("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "off"


async def test_device_house_decision_keeps_running_while_the_house_airs(hass, blueprints) -> None:
    await _device_automation(hass, "device_follows_room_action.yaml", "house")
    hass.bus.async_fire("freshairiq_room_recommendation", _recommendation("continue_ventilating", "ventilate"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "on"
    # the room alone would stop, the house keeps airing: the device stays on
    hass.bus.async_fire("freshairiq_room_action", _room_action("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "on"
    hass.bus.async_fire("freshairiq_room_recommendation", _recommendation("close", "continue_ventilating"))
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.bad_luefter").state == "off"
