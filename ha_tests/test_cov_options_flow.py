"""Real-HA coverage of the FreshAirIQ options flow (``FreshAirIQOptionsFlow``).

Every menu branch, the room wizard (add/edit/goals/contact references), HA area
import, sorting, levels, all settings pages and the persistence/runtime-apply
logic are driven against a real Home Assistant core.  Hidden compatibility
steps that no menu exposes are called on the live flow object and their result
is asserted.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.freshairiq.config_flow import DEFAULT_OPTIONS, FreshAirIQOptionsFlow
from custom_components.freshairiq.const import (
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    CONTACT_MODE_ANY,
    DOMAIN,
)


# --------------------------------------------------------------------------- helpers
def _room(name: str = "Wohnzimmer", *, key: str = "wohnzimmer", contacts=None, co2: bool = False, floor="EG") -> dict:
    room = {
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_TEMPERATURE: f"sensor.{key}_temperature",
        CONF_ROOM_HUMIDITY: f"sensor.{key}_humidity",
        CONF_ROOM_CONTACTS: list(contacts if contacts is not None else [f"binary_sensor.{key}_window"]),
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        CONF_ROOM_VOLUME: 55.0,
        CONF_ROOM_FLOOR: floor,
        CONF_ROOM_INCLUDE_CALCULATIONS: True,
    }
    if co2:
        room[CONF_ROOM_CO2] = f"sensor.{key}_co2"
    return room


def _entry(*, rooms=None, levels=None, options=None, subentries=None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            CONF_OUTDOOR_WEATHER: "weather.home",
            "rooms": list(rooms or []),
            "levels": list(["EG"] if levels is None else levels),
        },
        options=dict(options or {}),
        subentries_data=subentries or (),
    )


def _room_input(name: str, prefix: str, *, contacts=None, co2: bool = False, volume=40.0, floor="OG") -> dict:
    sensors = {
        CONF_ROOM_TEMPERATURE: [f"sensor.{prefix}_temperature"],
        CONF_ROOM_HUMIDITY: [f"sensor.{prefix}_humidity"],
        CONF_ROOM_CONTACTS: list(contacts or []),
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
    }
    if co2:
        sensors[CONF_ROOM_CO2] = f"sensor.{prefix}_co2"
    geometry = {} if volume is None else {CONF_ROOM_VOLUME: volume}
    return {
        "identity": {CONF_ROOM_NAME: name, CONF_ROOM_FLOOR: floor, CONF_ROOM_INCLUDE_CALCULATIONS: True},
        "sensors": sensors,
        "geometry": geometry,
    }


async def _open(hass, entry, *steps):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    for step in steps:
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": step})
    return result


async def _submit(hass, result, data):
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


def _flow(hass, result) -> FreshAirIQOptionsFlow:
    return hass.config_entries.options._progress[result["flow_id"]]


def _fake_coordinator() -> SimpleNamespace:
    return SimpleNamespace(
        async_rebuild_listeners=AsyncMock(),
        async_request_refresh=AsyncMock(),
        telemetry=SimpleNamespace(request_check=MagicMock()),
        store=SimpleNamespace(async_reset_learning=AsyncMock()),
    )


# --------------------------------------------------------------------------- basics / menus
async def test_working_copy_is_built_lazily_from_entry(hass) -> None:
    entry = _entry(rooms=[_room("B", key="b"), _room("A", key="a")], options={"start_rh": 61})
    entry.add_to_hass(hass)
    flow = FreshAirIQOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    flow._ensure_working_copy()

    assert flow._working_options["start_rh"] == 61
    assert "notifications_enabled" in flow._working_options  # DEFAULT_OPTIONS merged
    # rooms are sorted by persisted order index and renumbered
    assert [r["key"] for r in flow._rooms()] == ["b", "a"]
    assert [r["sort_order"] for r in flow._rooms()] == [0, 1]
    options = flow._room_selector().config["options"]
    assert options == [{"value": "b", "label": "B"}, {"value": "a", "label": "A"}]


async def test_compat_aliases_and_back_targets(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry)
    flow = _flow(hass, result)

    assert (await flow.async_step_comfort_health())["step_id"] == "ventilation_settings"
    assert (await flow.async_step_automation_costs())["step_id"] == "notification_energy_settings"
    assert (await flow.async_step_expert_data())["step_id"] == "data_learning_settings"
    assert (await flow.async_step_back())["step_id"] == "init"

    result = await _open(hass, entry, "home_setup", "back_to_main")
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "init"
    result = await _open(hass, entry, "home_setup", "rooms", "back_to_home_setup")
    assert result["step_id"] == "home_setup"


async def test_finish_commits_options_and_closes(hass) -> None:
    entry = _entry(rooms=[_room()], options={"start_rh": 63})
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "finish")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["start_rh"] == 63
    assert entry.options["start_rh"] == 63
    # legacy rooms were normalised and persisted on close
    assert entry.data["rooms"][0]["sort_order"] == 0


# --------------------------------------------------------------------------- persistence
async def test_persist_mirrors_room_subentries(hass) -> None:
    rooms = [_room(), _room("Bad", key="bad", floor="OG")]
    subentries = [
        ConfigSubentryData(data=dict(rooms[0]), subentry_type="room", title="Alt", unique_id="room:wohnzimmer"),
        ConfigSubentryData(data={"key": "stale"}, subentry_type="room", title="Stale", unique_id="room:stale"),
    ]
    entry = _entry(rooms=rooms, subentries=subentries)
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "levels")
    result = await _submit(hass, result, {"action": "add"})
    assert result["step_id"] == "level_add"
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit(hass, result, {"name": "Keller"})
    assert result["step_id"] == "levels"
    reload.assert_not_called()  # room keys unchanged -> no structural reload

    assert "Keller" in entry.data["levels"]
    by_unique = {s.unique_id: s for s in entry.subentries.values()}
    assert set(by_unique) == {"room:wohnzimmer", "room:bad"}
    assert by_unique["room:wohnzimmer"].title == "Wohnzimmer"
    assert by_unique["room:bad"].data["key"] == "bad"


async def test_persist_applies_runtime_changes_live(hass) -> None:
    # Options already complete, so the first page only changes what it submits.
    entry = _entry(rooms=[_room()], options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    coordinator = _fake_coordinator()
    entry.runtime_data = coordinator

    result = await _open(hass, entry, "home_setup", "outdoor")
    result = await _submit(hass, result, {CONF_OUTDOOR_WEATHER: "weather.other"})
    await hass.async_block_till_done()
    assert result["step_id"] == "home_setup"
    assert entry.data[CONF_OUTDOOR_WEATHER] == "weather.other"
    coordinator.async_rebuild_listeners.assert_awaited_once_with(invalidate_weather_cache=True)
    coordinator.async_request_refresh.assert_awaited()
    coordinator.telemetry.request_check.assert_not_called()

    coordinator.async_rebuild_listeners.reset_mock()
    result = await _open(hass, entry, "data_learning_settings", "diagnostics_sharing")
    assert result["step_id"] == "diagnostics_sharing"
    result = await _submit(hass, result, {"diagnostics_consent": "granted", "diagnostics_reporting_mode": "weekly"})
    await hass.async_block_till_done()
    assert result["step_id"] == "data_learning_settings"
    assert entry.options["diagnostics_consent"] == "granted"
    coordinator.async_rebuild_listeners.assert_not_called()
    coordinator.telemetry.request_check.assert_called_once()

    result = await _open(hass, entry, "ventilation_settings", "air_quality")
    result = await _submit(hass, result, {"voc_sensor_enabled": False})
    await hass.async_block_till_done()
    assert result["step_id"] == "ventilation_settings"
    coordinator.async_rebuild_listeners.assert_awaited_once_with(invalidate_weather_cache=False)


async def test_outdoor_validation_and_clearing(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "outdoor")
    result = await _submit(hass, result, {CONF_OUTDOOR_TEMPERATURE: "sensor.out_t"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outdoor_pair_required"}
    result = await _submit(hass, result, {CONF_OUTDOOR_TEMPERATURE: "sensor.out_t", CONF_OUTDOOR_HUMIDITY: "sensor.out_h"})
    assert result["step_id"] == "home_setup"
    assert CONF_OUTDOOR_WEATHER not in entry.data
    assert entry.data[CONF_OUTDOOR_HUMIDITY] == "sensor.out_h"


# --------------------------------------------------------------------------- room wizard
async def test_add_room_full_wizard_with_goals_and_contact_references(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    hass.states.async_set("binary_sensor.kueche_window", "off", {"friendly_name": "Küchenfenster"})
    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    assert result["step_id"] == "add_room"

    bad = _room_input("Küche", "kueche", volume=None)
    result = await _submit(hass, result, bad)
    assert result["errors"] == {"base": "room_volume_required"}

    contacts = ["binary_sensor.kueche_window", "binary_sensor.kueche_door"]
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit(hass, result, _room_input("Küche", "kueche", contacts=contacts, co2=True))
        assert result["step_id"] == "room_goals"
        # base room already persisted without reload
        assert [r["key"] for r in entry.data["rooms"]] == ["wohnzimmer", "kuche"]
        reload.assert_not_called()

        # an unknown goal (only possible from a stale form) is rejected on the page itself
        stale = await _flow(hass, result).async_step_room_goals({"goal_priority_1": "temperature", "goal_priority_2": "co2"})
        assert stale["step_id"] == "room_goals" and stale["errors"] == {"base": "invalid_goal_order"}
        result = await _submit(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "co2"})
        assert result["step_id"] == "contact_references"
        assert result["description_placeholders"]["contact_name"] == "Küchenfenster"
        assert result["description_placeholders"]["contact_position"] == "1"
        room = next(r for r in entry.data["rooms"] if r["key"] == "kuche")
        assert room[CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity"]

        # back on the first contact returns to the goal page
        result = await _submit(hass, result, {"wizard_back": True})
        assert result["step_id"] == "room_goals"
        result = await _submit(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "humidity"})
        assert result["step_id"] == "contact_references"

        # incomplete reference pair is rejected
        result = await _submit(hass, result, {"reference_temperature": "sensor.flur_t"})
        assert result["errors"] == {"base": "contact_reference_pair_required"}
        result = await _submit(hass, result, {
            "reference_temperature": "sensor.flur_t", "reference_humidity": "sensor.flur_h",
            "delay_seconds": 30, "orientation": "s",
        })
        assert result["description_placeholders"]["contact_position"] == "2"
        assert result["description_placeholders"]["contact_name"] == "Kueche Door"
        # back on the second contact goes to the first contact again
        result = await _submit(hass, result, {"wizard_back": True})
        assert result["description_placeholders"]["contact_position"] == "1"
        result = await _submit(hass, result, {"delay_seconds": 30, "orientation": "s",
                                               "reference_temperature": "sensor.flur_t", "reference_humidity": "sensor.flur_h"})
        result = await _submit(hass, result, {"delay_seconds": 5, "passage_door": True})
        assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"
        # the deferred structural reload runs once at the end of the wizard
        # (regression: test_options_add_room_reload_20261016.py)
        reload.assert_called_once_with(entry.entry_id)

    room = next(r for r in entry.data["rooms"] if r["key"] == "kuche")
    assert room[CONF_CONTACT_REFERENCE_TEMPERATURES] == {"binary_sensor.kueche_window": "sensor.flur_t"}
    assert room[CONF_CONTACT_REFERENCE_HUMIDITIES] == {"binary_sensor.kueche_window": "sensor.flur_h"}
    assert room[CONF_CONTACT_DELAYS] == {"binary_sensor.kueche_window": 30, "binary_sensor.kueche_door": 5}
    assert room["contact_passage_doors"]["binary_sensor.kueche_door"] is True
    assert room[CONF_ROOM_FLOOR] == "OG"


async def test_add_room_without_extra_goals_or_contacts_short_circuits(hass) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await _submit(hass, result, _room_input("Bad", "bad"))
    # single available goal -> goals page skipped; no contacts -> back to rooms
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"
    room = entry.data["rooms"][0]
    assert room[CONF_ROOM_GOAL_PRIORITIES] == ["humidity"]
    assert "edit_room_select" in result["menu_options"]


async def test_edit_room_flow_and_goal_back(hass) -> None:
    room = _room(contacts=["binary_sensor.w1", "binary_sensor.w2"], co2=True)
    room[CONF_CONTACT_ORIENTATIONS] = {"binary_sensor.w1": "n", "binary_sensor.w2": "e"}
    room[CONF_CONTACT_DELAYS] = {"binary_sensor.w1": 10, "binary_sensor.w2": 20}
    entry = _entry(rooms=[room])
    entry.add_to_hass(hass)

    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    assert result["step_id"] == "edit_room_select"
    result = await _submit(hass, result, {"wizard_back": True, "room": "wohnzimmer"})
    assert result["step_id"] == "rooms"

    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    assert result["step_id"] == "edit_room"
    assert result["description_placeholders"] == {"room_name": "Wohnzimmer"}

    bad = _room_input("", "wohnzimmer", contacts=["binary_sensor.w1"], co2=True)
    result = await _submit(hass, result, bad)
    assert result["step_id"] == "edit_room" and result["errors"][CONF_ROOM_NAME] == "room_name_required"

    result = await _submit(hass, result, _room_input("Wohnen", "wohnzimmer", contacts=["binary_sensor.w1"], co2=True, floor="EG"))
    assert result["step_id"] == "room_goals"
    stored = entry.data["rooms"][0]
    assert stored["key"] == "wohnzimmer" and stored[CONF_ROOM_NAME] == "Wohnen"
    assert stored[CONF_CONTACT_ORIENTATIONS] == {"binary_sensor.w1": "n"}
    assert stored[CONF_CONTACT_DELAYS] == {"binary_sensor.w1": 10}

    # back from goals reopens the edit page of the same room
    result = await _submit(hass, result, {"wizard_back": True})
    assert result["step_id"] == "edit_room"


async def test_room_wizard_missing_room_falls_back_to_rooms_menu(hass) -> None:
    entry = _entry(rooms=[_room(contacts=[])])
    entry.add_to_hass(hass)
    result = await _open(hass, entry)
    flow = _flow(hass, result)
    flow._selected_room_key = "missing"
    for step in (flow.async_step_room_goals, flow.async_step_edit_room, flow.async_step_contact_orientations,
                 flow.async_step_contact_delays, flow.async_step_contact_references):
        assert (await step())["step_id"] == "rooms"
    # no eligible room -> priority order falls back through the room picker to the section menu
    assert (await flow.async_step_recommendation_priority_order())["step_id"] == "ventilation_settings"

    # contactless room: orientation step persists with reload, delay step returns to menu
    flow._selected_room_key = "wohnzimmer"
    with patch.object(hass.config_entries, "async_schedule_reload"):
        assert (await flow.async_step_contact_orientations())["step_id"] == "rooms"
    assert (await flow.async_step_contact_delays())["step_id"] == "rooms"
    assert entry.data["rooms"][0]["sort_order"] == 0


async def test_hidden_contact_orientation_and_delay_steps(hass) -> None:
    room = _room(contacts=["binary_sensor.w1"])
    entry = _entry(rooms=[room])
    entry.add_to_hass(hass)
    result = await _open(hass, entry)
    flow = _flow(hass, result)

    form = await flow.async_step_contact_orientations_room()
    assert form["step_id"] == "contact_orientations_room"
    form = await flow.async_step_contact_orientations_room({"room": "wohnzimmer"})
    assert form["step_id"] == "contact_references"

    form = await flow.async_step_contact_orientations()
    assert form["step_id"] == "contact_orientations"
    assert form["description_placeholders"] == {"room_name": "Wohnzimmer"}
    form = await flow.async_step_contact_orientations({"binary_sensor.w1": "w"})
    assert form["step_id"] == "contact_delays"
    assert entry.data["rooms"][0][CONF_CONTACT_ORIENTATIONS] == {"binary_sensor.w1": "w"}

    form = await flow.async_step_contact_delays_room()
    assert form["step_id"] == "contact_delays_room"
    form = await flow.async_step_contact_delays_room({"room": "wohnzimmer"})
    assert form["step_id"] == "contact_delays"
    form = await flow.async_step_contact_delays({"binary_sensor.w1": 9999})
    assert form["step_id"] == "contact_references"
    assert entry.data["rooms"][0][CONF_CONTACT_DELAYS] == {"binary_sensor.w1": 600}


async def test_sort_rooms(hass) -> None:
    entry = _entry(rooms=[_room("A", key="a"), _room("B", key="b"), _room("C", key="c")])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "sort_rooms")
    assert result["step_id"] == "sort_rooms"
    flow = _flow(hass, result)
    schema_keys = [str(k) for k in result["data_schema"].schema]
    assert schema_keys == ["wizard_back", "room_position_1", "room_position_2", "room_position_3"]

    invalid = await flow.async_step_sort_rooms({"room_position_1": "a", "room_position_2": "zzz", "room_position_3": "c"})
    assert invalid["errors"] == {"base": "invalid_room_order"}

    back = await _submit(hass, result, {"wizard_back": True, "room_position_1": "a", "room_position_2": "b", "room_position_3": "c"})
    assert back["step_id"] == "rooms"

    result = await _open(hass, entry, "home_setup", "rooms", "sort_rooms")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit(hass, result, {"room_position_1": "c", "room_position_2": "b", "room_position_3": "c"})
    assert result["step_id"] == "rooms"
    reload.assert_not_called()
    # the chosen room moves to position 1; the duplicate slot is filled by the remaining room
    assert [r["key"] for r in entry.data["rooms"]] == ["c", "b", "a"]

    # empty installation: sort step falls back to the room menu
    empty = MockConfigEntry(domain=DOMAIN, data={"rooms": []})
    empty.add_to_hass(hass)
    res = await _open(hass, empty)
    menu = await _flow(hass, res).async_step_sort_rooms()
    assert menu["step_id"] == "rooms"
    assert menu["menu_options"] == ["add_room", "import_ha_rooms", "back_to_home_setup"]


async def test_remove_room(hass) -> None:
    entry = _entry(rooms=[_room("A", key="a"), _room("B", key="b")])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "remove_room")
    assert result["step_id"] == "remove_room"
    result = await _submit(hass, result, {"room": "a", "confirm": False})
    assert result["step_id"] == "rooms"
    assert len(entry.data["rooms"]) == 2

    result = await _open(hass, entry, "home_setup", "rooms", "remove_room")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit(hass, result, {"room": "a", "confirm": True})
    assert result["step_id"] == "rooms"
    assert [r["key"] for r in entry.data["rooms"]] == ["b"]
    reload.assert_called_once_with(entry.entry_id)


# --------------------------------------------------------------------------- HA area import
async def test_import_ha_rooms_without_areas_reports_error(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    ar.async_get(hass).async_create("Wohnzimmer")  # already configured -> not offered
    result = await _open(hass, entry, "home_setup", "rooms", "import_ha_rooms")
    assert result["step_id"] == "import_ha_rooms"
    assert result["errors"] == {"base": "no_ha_areas_to_import"}


async def test_import_ha_rooms_with_entity_suggestions(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    floor = fr.async_get(hass).async_create("Obergeschoss")
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    hass.states.async_set("sensor.area_pref_t", "21", {"device_class": "temperature"})
    kitchen = area_reg.async_create("Küche", floor_id=floor.floor_id, temperature_entity_id="sensor.area_pref_t")
    bath = area_reg.async_create("Bad")
    area_reg.async_create("Abstellraum")  # no entities at all

    def _reg(domain, uid, *, area=None, device=None, device_class=None, state=None, disabled=False):
        e = ent_reg.async_get_or_create(
            domain, "test", uid, suggested_object_id=uid, device_id=device,
            disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
        )
        if area:
            e = ent_reg.async_update_entity(e.entity_id, area_id=area)
        if device_class and state is None:
            e = ent_reg.async_update_entity(e.entity_id, device_class=device_class)
        if state is not None:
            hass.states.async_set(e.entity_id, state, {"device_class": device_class} if device_class else {})
        return e.entity_id

    t1 = _reg("sensor", "k_temp", area=kitchen.id, device_class="temperature", state="20")
    h1 = _reg("sensor", "k_hum", area=kitchen.id, device_class="humidity", state="50")
    co2 = _reg("sensor", "k_co2", area=kitchen.id, device_class="carbon_dioxide", state="600")
    lux = _reg("sensor", "k_lux", area=kitchen.id, device_class="illuminance", state="100")
    _reg("sensor", "k_power", area=kitchen.id, device_class="power", state="5")
    win = _reg("binary_sensor", "k_window", area=kitchen.id, device_class="window", state="off")
    _reg("binary_sensor", "k_motion", area=kitchen.id, device_class="motion", state="off")
    _reg("sensor", "k_disabled", area=kitchen.id, device_class="temperature", disabled=True)
    clim = _reg("climate", "k_climate", area=kitchen.id, state="heat")
    _reg("light", "k_light", area=kitchen.id, state="on")

    device = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "dev1")})
    dev_reg.async_update_device(device.id, area_id=bath.id)
    orphan = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "dev2")})
    bath_t = _reg("sensor", "b_temp", device=device.id, device_class="temperature")  # registry class, no state
    _reg("sensor", "b_other", device=orphan.id, device_class="humidity", state="40")  # device without area
    _reg("sensor", "b_unassigned", device_class="humidity", state="40")
    door = _reg("binary_sensor", "b_door", device=device.id, device_class="door", state="off")

    result = await _open(hass, entry, "home_setup", "rooms", "import_ha_rooms")
    assert result["step_id"] == "import_ha_rooms"
    flow = _flow(hass, result)
    choices, defaults = flow._ha_area_options()
    labels = {c["value"]: c["label"] for c in choices}
    assert labels[kitchen.id] == "Obergeschoss · Küche"
    assert labels[bath.id] == "Bad"
    assert defaults[kitchen.id][CONF_ROOM_TEMPERATURE] == ["sensor.area_pref_t", t1]
    assert defaults[kitchen.id][CONF_ROOM_HUMIDITY] == [h1]
    assert defaults[kitchen.id][CONF_ROOM_CO2] == co2
    assert defaults[kitchen.id][CONF_ROOM_ILLUMINANCE] == lux
    assert defaults[kitchen.id][CONF_ROOM_CLIMATE] == clim
    assert defaults[kitchen.id][CONF_ROOM_CONTACTS] == [win]
    assert defaults[bath.id] == {CONF_ROOM_NAME: "Bad", CONF_ROOM_FLOOR: "Unassigned",
                                 CONF_ROOM_TEMPERATURE: [bath_t], CONF_ROOM_CONTACTS: [door]}
    assert flow._ha_area_entity_defaults("no-such-area") == {}

    # empty selection is rejected, then a single string selection works
    res = await flow.async_step_import_ha_rooms({"areas": []})
    assert res["errors"] == {"base": "select_ha_area"}
    res = await flow.async_step_import_ha_rooms({"areas": bath.id})
    assert res["step_id"] == "import_ha_room_details"
    assert res["description_placeholders"] == {"room_name": "Bad", "remaining": "1"}

    # now through the manager: two areas, detail validation error, then complete both
    result = await _open(hass, entry, "home_setup", "rooms", "import_ha_rooms")
    result = await _submit(hass, result, {"areas": [kitchen.id, bath.id]})
    assert result["step_id"] == "import_ha_room_details"
    assert result["description_placeholders"] == {"room_name": "Küche", "remaining": "2"}
    kitchen_input = {
        "identity": {CONF_ROOM_NAME: "Küche", CONF_ROOM_FLOOR: "Obergeschoss", CONF_ROOM_INCLUDE_CALCULATIONS: True},
        "sensors": {CONF_ROOM_TEMPERATURE: [t1], CONF_ROOM_HUMIDITY: [h1], CONF_ROOM_CONTACTS: [win]},
        "geometry": {},
    }
    result = await _submit(hass, result, kitchen_input)
    assert result["step_id"] == "import_ha_room_details"
    assert result["errors"] == {"base": "room_volume_required"}
    kitchen_input["geometry"] = {CONF_ROOM_VOLUME: 30}
    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await _submit(hass, result, kitchen_input)
        assert result["description_placeholders"] == {"room_name": "Bad", "remaining": "1"}
        result = await _submit(hass, result, {
            "identity": {CONF_ROOM_NAME: "Bad", CONF_ROOM_FLOOR: "EG", CONF_ROOM_INCLUDE_CALCULATIONS: False},
            "sensors": {}, "geometry": {},
        })
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "rooms"
    names = [r[CONF_ROOM_NAME] for r in entry.data["rooms"]]
    assert names == ["Wohnzimmer", "Küche", "Bad"]
    assert entry.data["levels"] == ["EG", "Obergeschoss"]


# --------------------------------------------------------------------------- levels
async def test_levels_add_reorder_remove_back(hass) -> None:
    entry = _entry(rooms=[_room(floor="Dach")], levels=["EG", "OG"])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "levels")
    assert result["step_id"] == "levels"
    assert "Dach" in result["description_placeholders"]["levels"]

    result = await _submit(hass, result, {"action": "add"})
    result = await _submit(hass, result, {"name": "OG"})  # duplicate ignored
    assert result["step_id"] == "levels"

    result = await _submit(hass, result, {"action": "reorder"})
    assert result["step_id"] == "level_reorder"
    keys = [str(k) for k in result["data_schema"].schema]
    assert len(keys) == 3
    result = await _submit(hass, result, {keys[0]: 3, keys[1]: 1, keys[2]: 2})
    assert result["step_id"] == "levels"
    assert entry.data["levels"] == ["OG", "Dach", "EG"]

    result = await _submit(hass, result, {"action": "remove"})
    assert result["step_id"] == "level_remove"
    opts = [o["value"] for o in result["data_schema"].schema["name"].config["options"]]
    assert "Dach" not in opts
    result = await _submit(hass, result, {"name": "OG"})
    assert result["step_id"] == "levels"
    assert entry.data["levels"] == ["Dach", "EG"]

    result = await _submit(hass, result, {"action": "back"})
    assert result["step_id"] == "home_setup"


async def test_levels_empty_reorder_and_nothing_removable(hass) -> None:
    entry = _entry(levels=[])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "levels")
    assert result["description_placeholders"]["levels"] == "No areas yet"
    result = await _submit(hass, result, {"action": "reorder"})
    assert result["step_id"] == "levels"
    result = await _submit(hass, result, {"action": "remove"})
    assert result["step_id"] == "levels"


# --------------------------------------------------------------------------- ventilation settings
@pytest.mark.parametrize(
    ("mode", "next_step", "value_key", "value"),
    [
        ("percent_total_water", "threshold_percent", "min_potential_percent_total_water", 12.5),
        ("fixed_ml", "threshold_fixed", "min_potential_total_ml", 800),
        ("adaptive_home_size", None, None, None),
    ],
)
async def test_threshold_modes(hass, mode, next_step, value_key, value) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "threshold")
    assert result["step_id"] == "threshold"
    result = await _submit(hass, result, {"threshold_mode": mode})
    assert entry.options["threshold_mode"] == mode
    if next_step is None:
        assert result["step_id"] == "ventilation_settings"
        return
    assert result["step_id"] == next_step
    result = await _submit(hass, result, {value_key: value})
    assert result["step_id"] == "ventilation_settings"
    assert entry.options[value_key] == float(value)
    assert entry.options["threshold_mode"] == mode


async def test_model_relationship_error_then_save(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "model")
    sections = {k: {} for k in ("humidity_thresholds", "recommendation_thresholds", "ventilation_timing",
                                 "efficiency", "health_limits", "learning")}
    bad = {**sections, "humidity_thresholds": {"target_rh": 70, "start_rh": 60, "high_rh": 68}}
    result = await _submit(hass, result, bad)
    assert result["errors"] == {"base": "invalid_humidity_order"}
    good = {**sections, "humidity_thresholds": {"target_rh": 55, "start_rh": 60, "high_rh": 70}}
    result = await _submit(hass, result, good)
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["start_rh"] == 60 and entry.options["high_rh"] == 70


async def test_recommendation_priorities(hass) -> None:
    entry = _entry(rooms=[_room(co2=True), _room("Flur", key="flur")])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "recommendation_priorities")
    assert result["step_id"] == "recommendation_priorities"
    room_opts = result["data_schema"].schema["room"].config["options"]
    assert room_opts == [{"value": "wohnzimmer", "label": "Wohnzimmer"}]

    back = await _submit(hass, result, {"wizard_back": True, "room": "wohnzimmer"})
    assert back["step_id"] == "ventilation_settings"

    result = await _open(hass, entry, "ventilation_settings", "recommendation_priorities")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    assert result["step_id"] == "recommendation_priority_order"
    result = await _submit(hass, result, {"wizard_back": True})
    assert result["step_id"] == "recommendation_priorities"
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    stale = await _flow(hass, result).async_step_recommendation_priority_order(
        {"goal_priority_1": "temperature", "goal_priority_2": "humidity"}
    )
    assert stale["errors"] == {"base": "invalid_goal_order"}
    result = await _submit(hass, result, {"goal_priority_1": "co2", "goal_priority_2": "humidity"})
    assert result["step_id"] == "recommendation_priorities"
    assert entry.data["rooms"][0][CONF_ROOM_GOAL_PRIORITIES] == ["co2", "humidity"]

    flow = _flow(hass, result)
    flow._selected_room_key = "missing"
    assert (await flow.async_step_recommendation_priority_order())["step_id"] == "recommendation_priorities"


async def test_recommendation_priorities_without_eligible_rooms(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "recommendation_priorities")
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "ventilation_settings"


async def test_cross_ventilation_and_forecast(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "cross_ventilation")
    assert result["description_placeholders"] == {"room_keys": "Wohnzimmer = wohnzimmer"}
    result = await _submit(hass, result, {"cross_ventilation_pairs": "wohnzimmer:bad"})
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["cross_ventilation_pairs"] == "wohnzimmer:bad"

    empty = MockConfigEntry(domain=DOMAIN, data={"rooms": []})
    empty.add_to_hass(hass)
    result = await _open(hass, empty, "ventilation_settings", "cross_ventilation")
    assert result["description_placeholders"] == {"room_keys": "No rooms set up yet"}

    result = await _open(hass, entry, "ventilation_settings", "forecast")
    result = await _submit(hass, result, {"forecast_horizon_min": 30})
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["forecast_horizon_min"] == 30


async def test_profile_summer_cooling_details(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "profile")
    result = await _submit(hass, result, {"operating_profile": "summer_cooling"})
    assert result["step_id"] == "profile_details"
    assert result["description_placeholders"] == {"profile": "Summer cooling"}
    result = await _submit(hass, result, {})
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["operating_profile"] == "summer_cooling"

    result = await _open(hass, entry, "ventilation_settings", "profile")
    result = await _submit(hass, result, {"operating_profile": "dehumidify"})
    assert result["step_id"] == "ventilation_settings"
    flow = _flow(hass, result)
    assert (await flow.async_step_profile_details())["step_id"] == "ventilation_settings"


async def test_profile_comfort_details_offer_the_cooling_lower_limit(hass) -> None:
    """0.26.5.4 (GitHub #19): the house-wide cooling start also limits the comfort profile, so it can be set there."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "profile")
    result = await _submit(hass, result, {"operating_profile": "comfort"})
    assert result["step_id"] == "profile_details"
    assert result["description_placeholders"] == {"profile": "Comfort"}
    assert [str(key) for key in result["data_schema"].schema] == ["cooling_start_temp_c"]
    result = await _submit(hass, result, {"cooling_start_temp_c": 25.5})
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["operating_profile"] == "comfort"
    assert entry.options["cooling_start_temp_c"] == 25.5


# --------------------------------------------------------------------------- home setup pages
async def test_building_page_saves(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "building")
    result = await _submit(hass, result, {})
    assert result["step_id"] == "home_setup"
    assert entry.options  # building defaults persisted


async def test_residents_structured_profiles(hass) -> None:
    profiles = {"adult:0": {"name": "Anna", "room_keys": [], "thermal_preference": "cool",
                            "notification_targets": ["old"]}}
    entry = _entry(rooms=[_room()], options={"resident_room_profiles": json.dumps(profiles),
                                             "adult_occupants": 2, "child_occupants": 1})
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "residents")
    assert result["step_id"] == "residents"
    assert "resident_slots" in result["description_placeholders"]

    result = await _submit(hass, result, {
        "residents": {"adult_occupants": 2, "adult_resident_names": "Anna, Ben", "child_occupants": 1,
                      "child_resident_names": "Cleo"},
        "resident_profiles": {"adult_2_rooms": ["wohnzimmer"], "adult_2_thermal": "warm",
                              "adult_2_notifications": "phone; tablet"},
    })
    assert result["step_id"] == "home_setup"
    stored = json.loads(entry.options["resident_room_profiles"])
    assert stored["adult:1"] == {"name": "Ben", "room_keys": ["wohnzimmer"], "thermal_preference": "warm",
                                 "notification_targets": ["phone", "tablet"]}
    assert stored["child:0"]["name"] == "Cleo"
    assert entry.options["adult_resident_names"] == "Anna, Ben"


async def test_residents_raw_profile_string_validation(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry)
    flow = _flow(hass, result)

    for invalid in ("[1, 2]", "{not json"):
        form = await flow.async_step_residents({"resident_room_profiles": invalid})
        assert form["step_id"] == "residents"
        assert form["errors"] == {"base": "resident_profiles_invalid"}

    menu = await flow.async_step_residents({"resident_room_profiles": '{ "adult:0": {"name": "Ä"} }'})
    assert menu["step_id"] == "home_setup"
    assert entry.options["resident_room_profiles"] == '{"adult:0":{"name":"Ä"}}'


async def test_legacy_house_and_personalisation_routes(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry)
    flow = _flow(hass, result)

    assert (await flow.async_step_house())["step_id"] == "home_setup"
    assert (await flow.async_step_house({"floor_area_m2": 99}))["step_id"] == "home_setup"
    assert entry.options["floor_area_m2"] == 99
    assert (await flow.async_step_personalisation())["step_id"] == "residents"
    assert (await flow.async_step_personalisation({"thermal_preference": "warm"}))["step_id"] == "home_setup"
    assert entry.options["thermal_preference"] == "warm"


# --------------------------------------------------------------------------- notifications / energy
async def test_notifications_test_send_variants(hass) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    entry = _entry(rooms=[_room()], options={"notification_targets": ["ghost"]})
    entry.add_to_hass(hass)

    result = await _open(hass, entry, "notification_energy_settings", "notifications")
    assert result["step_id"] == "notifications"
    result = await _submit(hass, result, {"notification_targets": ["ghost"], "test_notification_now": True})
    assert result["errors"] == {"test_notification_now": "notification_test_failed"}

    result = await _submit(hass, result, {"notification_targets": [], "test_notification_now": True})
    assert result["errors"] == {"test_notification_now": "notification_test_no_target"}

    result = await _submit(hass, result, {"notification_targets": ["phone"], "test_notification_now": True})
    await hass.async_block_till_done()
    assert result["step_id"] == "notifications" and not result["errors"]
    assert len(calls) == 1 and calls[0].data["title"] == "FreshAirIQ · Test"

    result = await _submit(hass, result, {"notification_targets": ["phone"]})
    assert result["step_id"] == "notification_energy_settings"
    assert entry.options["notification_targets"] == ["phone"]
    assert "test_notification_now" not in entry.options


@pytest.mark.parametrize(
    ("system", "label", "detail"),
    [
        ("heat_pump", "Heat pump", {"heat_pump_cop": 4.0}),
        ("gas", "Gas heating", {"gas_efficiency": 0.9}),
        ("oil", "Oil heating", {"oil_efficiency": 0.8}),
        ("district_heating", "District heating", {"district_efficiency": 0.95}),
        ("electric", "Electric heating", {"electricity_price_per_kwh": 0.4}),
    ],
)
async def test_energy_details_per_heating_system(hass, system, label, detail) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "notification_energy_settings", "energy")
    result = await _submit(hass, result, {"heating_system": system})
    assert result["step_id"] == "energy_details"
    assert result["description_placeholders"] == {"heating_system": label}
    result = await _submit(hass, result, detail)
    assert result["step_id"] == "notification_energy_settings"
    assert entry.options["heating_system"] == system
    key, value = next(iter(detail.items()))
    assert entry.options[key] == value


# --------------------------------------------------------------------------- data / maintenance
async def test_statistics_and_diagnostics_sharing(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "data_learning_settings", "statistics")
    result = await _submit(hass, result, {"statistics_days": 30})
    assert result["step_id"] == "data_learning_settings"
    assert entry.options["statistics_days"] == 30

    result = await _open(hass, entry, "data_learning_settings", "diagnostics_sharing")
    result = await _submit(hass, result, {"diagnostics_consent": "declined"})
    assert result["step_id"] == "data_learning_settings"
    assert entry.options["diagnostics_consent"] == "declined"


async def test_reset_defaults(hass) -> None:
    entry = _entry(rooms=[_room()], options={"start_rh": 70})
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "maintenance", "reset_defaults")
    result = await _submit(hass, result, {"confirm": False})
    assert result["step_id"] == "maintenance"
    assert entry.options["start_rh"] == 70
    result = await _open(hass, entry, "maintenance", "reset_defaults")
    result = await _submit(hass, result, {"confirm": True})
    assert result["step_id"] == "maintenance"
    assert entry.options["start_rh"] != 70


async def test_reset_learning_with_and_without_coordinator(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "maintenance", "reset_learning")
    result = await _submit(hass, result, {"confirm": True})  # no runtime data -> no-op
    assert result["step_id"] == "maintenance"

    coordinator = _fake_coordinator()
    entry.runtime_data = coordinator
    result = await _open(hass, entry, "maintenance", "reset_learning")
    result = await _submit(hass, result, {"confirm": False})
    coordinator.store.async_reset_learning.assert_not_awaited()
    result = await _open(hass, entry, "maintenance", "reset_learning")
    result = await _submit(hass, result, {"confirm": True})
    assert result["step_id"] == "maintenance"
    coordinator.store.async_reset_learning.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited()
