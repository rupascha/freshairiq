"""0.26.5.1 (owner request): FreshAirIQ may control covers and exhaust fans – opt-in.

Real Home Assistant setup: the settings (per opening "open the cover with the
window", per room "close covers against the sun" and "switch the exhaust fan")
are stored by the flows, and the controller moves the covers / switches the fan
through Home Assistant services. A passage door's cover never closes while the
door is open. Rooms without these options are never touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq import config_flow as cf
from custom_components.freshairiq.const import (
    CONF_CONTACT_COVER_FOLLOW,
    CONF_CONTACT_COVERS,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_PASSAGE_DOORS,
    CONF_ROOM_AUTO_SUN_PROTECTION,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_FAN_CONTROL,
    CONF_ROOM_EXHAUST_FAN_FOLLOW_UP,
    CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME,
    DEFAULT_OPTIONS,
)
from ha_tests import test_cov_options_flow as opt
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

WINDOW = "binary_sensor.wohnzimmer_window"
DOOR = "sensor.balkontuer"
COVER = "cover.wohnzimmer"
DOOR_COVER = "cover.balkon"
FAN = "switch.bad_luefter"
POSITION_COVER = {"current_position": 0, "supported_features": 15}


# --------------------------------------------------------------------------- settings
def test_opening_form_offers_the_follow_option_only_with_covers() -> None:
    room = {**opt._room(contacts=[WINDOW])}
    schema = cf._single_contact_reference_schema(room, WINDOW)
    assert "cover_follow" in {str(k) for k in schema.schema}
    form = {"delay_seconds": 0, "orientation": "s", "cover_position_zero_means": "closed", "passage_door": False}
    assert cf._apply_single_contact_reference(room, WINDOW, {**form, "covers": [COVER], "cover_follow": True})
    assert room[CONF_CONTACT_COVER_FOLLOW] == {WINDOW: True}
    defaults = {str(k): k.default() for k in cf._single_contact_reference_schema(room, WINDOW).schema if hasattr(k, "default") and callable(k.default)}
    assert defaults["cover_follow"] is True
    assert cf._apply_single_contact_reference(room, WINDOW, {**form, "covers": [], "cover_follow": True})
    assert room[CONF_CONTACT_COVER_FOLLOW] == {WINDOW: False}


def test_room_form_keeps_and_validates_the_control_settings() -> None:
    previous = {**opt._room(contacts=[WINDOW, "binary_sensor.alt"]), CONF_CONTACT_COVERS: {WINDOW: [COVER], "binary_sensor.alt": [COVER]},
                CONF_CONTACT_COVER_FOLLOW: {WINDOW: True, "binary_sensor.gone": True},
                CONF_ROOM_AUTO_SUN_PROTECTION: True, CONF_ROOM_EXHAUST_FAN_CONTROL: "moisture_source",
                CONF_ROOM_EXHAUST_FAN_FOLLOW_UP: 15, CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME: 90}
    flat = cf._flatten_sections(opt._room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW]))
    room, errors = cf._normalise_room(flat, [previous], keep_key="wohnzimmer")
    assert errors == {}
    assert room[CONF_CONTACT_COVER_FOLLOW] == {WINDOW: True}
    assert (room[CONF_ROOM_AUTO_SUN_PROTECTION], room[CONF_ROOM_EXHAUST_FAN_CONTROL]) == (True, "moisture_source")
    assert (room[CONF_ROOM_EXHAUST_FAN_FOLLOW_UP], room[CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME]) == (15, 90)

    flat.update({CONF_ROOM_AUTO_SUN_PROTECTION: False, CONF_ROOM_EXHAUST_FAN_CONTROL: "bogus",
                 CONF_ROOM_EXHAUST_FAN_FOLLOW_UP: 500, CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME: 1})
    room, _ = cf._normalise_room(flat, [previous], keep_key="wohnzimmer")
    assert (room[CONF_ROOM_AUTO_SUN_PROTECTION], room[CONF_ROOM_EXHAUST_FAN_CONTROL]) == (False, "off")
    assert (room[CONF_ROOM_EXHAUST_FAN_FOLLOW_UP], room[CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME]) == (60, 5)

    new, _ = cf._normalise_room(cf._flatten_sections(opt._room_input("Bad", "bad")), [previous])
    assert (new[CONF_ROOM_AUTO_SUN_PROTECTION], new[CONF_ROOM_EXHAUST_FAN_CONTROL]) == (False, "off")
    assert (new[CONF_ROOM_EXHAUST_FAN_FOLLOW_UP], new[CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME]) == (10, 60)


async def test_edit_room_saves_the_automation_section(hass) -> None:
    entry = opt._entry(rooms=[opt._room(contacts=[WINDOW])])
    entry.add_to_hass(hass)
    result = await opt._open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await opt._submit(hass, result, {"room": "wohnzimmer"})
    assert result["step_id"] == "edit_room"
    assert "automation" in {str(k) for k in result["data_schema"].schema}
    data = opt._room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW], floor="EG")
    data["automation"] = {CONF_ROOM_AUTO_SUN_PROTECTION: True, CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation",
                          CONF_ROOM_EXHAUST_FAN_FOLLOW_UP: 5, CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME: 45}
    result = await opt._submit(hass, result, data)
    assert result["step_id"] == "contact_references"  # no CO2 sensor: no goal page
    stored = entry.data["rooms"][0]
    assert stored[CONF_ROOM_AUTO_SUN_PROTECTION] is True and stored[CONF_ROOM_EXHAUST_FAN_CONTROL] == "recommendation"
    assert "cover_follow" in {str(k) for k in result["data_schema"].schema}

    flow = opt._flow(hass, result)
    with patch.object(hass.config_entries, "async_schedule_reload"):
        await flow.async_step_contact_references({"delay_seconds": 0, "orientation": "s", "covers": [COVER],
                                                  "cover_position_zero_means": "closed", "passage_door": False, "cover_follow": True})
    assert entry.data["rooms"][0][CONF_CONTACT_COVER_FOLLOW] == {WINDOW: True}


# --------------------------------------------------------------------------- controller
def _services(hass) -> dict:
    return {name: async_mock_service(hass, "cover", name) for name in ("open_cover", "close_cover", "stop_cover", "set_cover_position")} | {
        "turn_on": async_mock_service(hass, "homeassistant", "turn_on"),
        "turn_off": async_mock_service(hass, "homeassistant", "turn_off"),
    }


def _calls(calls) -> list:
    return [(call.data["entity_id"], call.data.get("position")) for call in calls]


async def _state(hass, entity_id: str, state: str, attributes: dict | None = None) -> None:
    hass.states.async_set(entity_id, state, attributes or {})
    await hass.async_block_till_done()


def _cover_room(**extra) -> dict:
    room = {**_room(), CONF_ROOM_CONTACTS: [WINDOW, DOOR],
            CONF_CONTACT_COVERS: {WINDOW: [COVER], DOOR: [DOOR_COVER]},
            CONF_CONTACT_COVER_FOLLOW: {WINDOW: True}, CONF_CONTACT_PASSAGE_DOORS: {DOOR: True},
            CONF_CONTACT_ORIENTATIONS: {WINDOW: "s", DOOR: "s"}}
    room.update(extra)
    return room


async def test_window_opens_the_cover_and_restores_its_position(hass, hass_storage) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(DOOR, "closed")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    hass.states.async_set(DOOR_COVER, "open", {"current_position": 100, "supported_features": 15})
    entry = await _setup(hass, _entry(rooms=[_cover_room()]))
    assert all(not c for c in calls.values())  # nothing happens without a change

    await _state(hass, WINDOW, "on")
    assert _calls(calls["open_cover"]) == [(COVER, None)]
    await _state(hass, COVER, "open", {"current_position": 100, "supported_features": 15})
    await _state(hass, WINDOW, "off")
    assert _calls(calls["set_cover_position"]) == [(COVER, 0)]

    # passage door: a close started by anyone is stopped and reversed while it is open
    await _state(hass, DOOR, "open")
    await _state(hass, DOOR_COVER, "closing", {"current_position": 80, "supported_features": 15})
    assert _calls(calls["stop_cover"]) == [(DOOR_COVER, None)]
    assert _calls(calls["open_cover"])[-1] == (DOOR_COVER, None)
    await _unload(hass, entry)
    stored = hass_storage[f"freshairiq.actuators.{entry.entry_id}"]["data"]
    assert stored["covers"][COVER]["follow_active"] is False


async def test_a_restart_restores_a_cover_opened_before(hass, hass_storage) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(DOOR, "closed")
    hass.states.async_set(COVER, "open", {"current_position": 100, "supported_features": 15})
    entry = _entry(rooms=[_cover_room()])
    hass_storage[f"freshairiq.actuators.{entry.entry_id}"] = {
        "version": 1, "key": f"freshairiq.actuators.{entry.entry_id}",
        "data": {"covers": {COVER: {"follow_active": True, "restore_position": 20, "restore_closed": False}}, "fans": {}},
    }
    entry = await _setup(hass, entry)
    assert _calls(calls["set_cover_position"]) == [(COVER, 20)]
    await _unload(hass, entry)


async def test_sun_protection_closes_the_covers_in_the_sun(hass, freezer) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set("sensor.wohnzimmer_temperature", "27", {"unit_of_measurement": "°C"})
    hass.config.latitude, hass.config.longitude = 52.52, 13.405
    freezer.move_to(datetime(2026, 7, 15, 11, 20, tzinfo=timezone.utc))  # sun in the south
    hass.states.async_set(DOOR, "open")
    hass.states.async_set(COVER, "open", {"current_position": 100, "supported_features": 15})
    hass.states.async_set(DOOR_COVER, "open", {"current_position": 100, "supported_features": 15})
    entry = await _setup(hass, _entry(rooms=[_cover_room(**{CONF_ROOM_AUTO_SUN_PROTECTION: True})],
                                     options={**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}))
    # the window cover closes, the cover of the open passage door waits
    assert _calls(calls["close_cover"]) == [(COVER, None)]
    await _state(hass, DOOR, "closed")
    assert _calls(calls["close_cover"]) == [(COVER, None), (DOOR_COVER, None)]

    # the sun moves away: FreshAirIQ reopens what it closed
    await _state(hass, COVER, "closed", {"current_position": 0, "supported_features": 15})
    await _state(hass, DOOR_COVER, "closed", {"current_position": 0, "supported_features": 15})
    freezer.move_to(datetime(2026, 7, 15, 17, 30, tzinfo=timezone.utc))  # sun in the west
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert sorted(_calls(calls["open_cover"])) == [(DOOR_COVER, None), (COVER, None)]
    await _unload(hass, entry)


async def test_exhaust_fan_after_a_moisture_source(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(FAN, "off")
    room = {**_room(), CONF_ROOM_EXHAUST_FAN: [FAN], CONF_ROOM_EXHAUST_FAN_CONTROL: "moisture_source", CONF_ROOM_EXHAUST_FAN_FOLLOW_UP: 0}
    entry = await _setup(hass, _entry(rooms=[room]))
    coordinator = entry.runtime_data
    coordinator.data["rooms"]["wohnzimmer"]["moisture_source_active"] = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert _calls(calls["turn_on"]) == [([FAN], None)]
    hass.states.async_set(FAN, "on")
    coordinator.data["rooms"]["wohnzimmer"]["moisture_source_active"] = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert _calls(calls["turn_off"]) == [([FAN], None)]
    await _unload(hass, entry)


async def test_rooms_without_control_are_never_touched(hass, hass_storage) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(COVER, "closed", POSITION_COVER)
    room = {**_room(), CONF_CONTACT_COVERS: {WINDOW: [COVER]}, CONF_ROOM_EXHAUST_FAN: [FAN]}
    entry = await _setup(hass, _entry(rooms=[room]))
    await _state(hass, WINDOW, "on")
    await _state(hass, WINDOW, "off")
    assert all(not c for c in calls.values())
    await _unload(hass, entry)
    assert f"freshairiq.actuators.{entry.entry_id}" not in hass_storage


async def test_unavailable_devices_and_failing_services(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(FAN, "unavailable")
    hass.states.async_set(DOOR, "closed")
    hass.states.async_set(COVER, "closed", {"current_position": "x", "supported_features": "y"})
    room = _cover_room(**{CONF_ROOM_EXHAUST_FAN: FAN, CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation"})
    entry = await _setup(hass, _entry(rooms=[room]))
    # no cover service registered: the failing call is logged, the controller keeps running
    await _state(hass, WINDOW, "on")
    controller = entry.runtime_data.actuator_controller
    assert controller._memory["covers"][COVER]["follow_active"] is True
    assert controller._cover_view("cover.missing", False).available is False
    await _unload(hass, entry)
