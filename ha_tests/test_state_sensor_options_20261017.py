"""Community (2026-10-17): for the room action entity the automation editor only
offered "any state / unavailable / unknown" as state trigger, while a window
entity offers open/closed.

The state sensors (action, recommendation, mould risk, learning status) now
declare their fixed vocabulary as an enum, so Home Assistant lists the
translated states. The state values are unchanged. Real Home Assistant setup.
"""
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.helpers import entity_registry as er

from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.sensor import ACTION_STATE_MAP, ROOM_ENUM_OPTIONS
from ha_tests.test_cov_setup_and_platforms import _entry, _set_sources, _setup, _unload

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"


def _entity_id(hass, field: str) -> str:
    registry = er.async_get(hass)
    return next(e.entity_id for e in registry.entities.values()
                if e.platform == DOMAIN and e.unique_id.endswith(f"wohnzimmer_{field}"))


async def test_state_sensors_offer_their_states_to_automations(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    for field in ("action", "house_aligned_action", "mould_level", "learning_status"):
        state = hass.states.get(_entity_id(hass, field))
        assert state is not None, field
        assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM, field
        assert state.attributes[ATTR_OPTIONS] == ROOM_ENUM_OPTIONS[field], field
        assert state.state in state.attributes[ATTR_OPTIONS], (field, state.state)
    action = hass.states.get(_entity_id(hass, "action"))
    for code in ("close", "ventilate", "continue_ventilating", "wait", "okay", "ventilate_indirectly"):
        assert code in action.attributes[ATTR_OPTIONS]
    await _unload(hass, entry)


async def test_unknown_values_stay_valid_states(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    coordinator.data["rooms"]["wohnzimmer"]["action"] = "Something new"
    coordinator.data["rooms"]["wohnzimmer"]["house_aligned_action"] = "something_new"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(_entity_id(hass, "action")).state == "unknown"
    assert hass.states.get(_entity_id(hass, "house_aligned_action")).state == "unknown"
    await _unload(hass, entry)


def test_every_option_is_translated() -> None:
    assert set(ACTION_STATE_MAP.values()) <= set(ROOM_ENUM_OPTIONS["action"])
    for language in ("de", "en"):
        sensors = json.loads((COMP / "translations" / f"{language}.json").read_text(encoding="utf-8"))["entity"]["sensor"]
        for field, options in ROOM_ENUM_OPTIONS.items():
            states = sensors[field]["state"]
            missing = [option for option in options if option not in states]
            assert not missing, (language, field, missing)
