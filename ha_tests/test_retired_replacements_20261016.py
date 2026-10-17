"""Replacements (2026-10-16) for tests retired with the dashboard settings centre.

0.26.4.3 removed the card-based settings centre and its write API; Devices &
services (``FreshAirIQOptionsFlow`` and the room subentry flow) is the only
settings surface. The retired tests checked intents that still apply to that
native surface: every setting is reachable, only the active threshold value is
written, runtime changes apply live without a reload, room editors keep the
per-opening contract, and so on. Each test below names the retired test(s) it
replaces and checks the same intent against a real Home Assistant core.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData, section
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq.config_flow import DEFAULT_OPTIONS
from custom_components.freshairiq.const import (
    CONF_CONTACT_MODE,
    CONF_CONTACT_PASSAGE_DOORS,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25_ENTITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_MOISTURE_SOURCES,
    CONF_ROOM_NAME,
    CONF_ROOM_REFERENCE_HUMIDITY,
    CONF_ROOM_REFERENCE_TEMPERATURE,
    CONF_ROOM_TEMPERATURE,
    CONTACT_MODE_ANY,
    DOMAIN,
    MOISTURE_SOURCES,
)
from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS

from ha_tests.test_cov_options_flow import (
    _entry,
    _fake_coordinator,
    _flow,
    _open,
    _room,
    _room_input,
    _submit,
)
from ha_tests.test_cov_room_subentry_flow import _start, fast_commit_sleep  # noqa: F401 - fixture
from ha_tests.test_cov_setup_and_platforms import (
    _entry as _setup_entry,
    _set_sources,
    _setup,
    _unload,
)

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"
DOOR = "binary_sensor.wohnzimmer_door"
WINDOW = "binary_sensor.wohnzimmer_window"


# --------------------------------------------------------------------------- helpers
def _schema_fields(schema: vol.Schema, parent: str | None = None) -> list[tuple[str | None, str, object]]:
    """Every field of a rendered form as (section, key, selector), sections flattened."""
    fields: list[tuple[str | None, str, object]] = []
    for marker, value in schema.schema.items():
        if isinstance(value, section):
            fields.extend(_schema_fields(value.schema, str(marker)))
        else:
            fields.append((parent, str(marker), value))
    return fields


def _keys(result) -> list[str]:
    return [key for _section, key, _value in _schema_fields(result["data_schema"])]


def _field(result, key: str):
    for _section, name, value in _schema_fields(result["data_schema"]):
        if name == key:
            return value
    raise AssertionError(f"{key} not on form {result['step_id']}")


def _default(result, key: str):
    def _walk(schema):
        for marker, value in schema.schema.items():
            if isinstance(value, section):
                found = _walk(value.schema)
                if found is not None:
                    return found
            elif str(marker) == key:
                return marker.default() if callable(marker.default) else marker.default
        return None

    return _walk(result["data_schema"])


def _rich_room(**extra) -> dict:
    """Room with every goal source so the goal ranking page is shown."""
    room = _room(contacts=[WINDOW], co2=True)
    room.update(extra)
    return room


async def _all_native_forms(hass) -> dict[str, list]:
    """Render every user-visible options page, including every branch page."""
    entry = _entry(
        rooms=[_rich_room(climate="climate.wohnzimmer")],
        options={"adult_occupants": 1, "adult_resident_names": "Anna", "child_occupants": 1},
    )
    entry.add_to_hass(hass)
    forms: dict[str, list] = {}

    async def render(name: str, *path: str, submit: dict | None = None):
        result = await _open(hass, entry, *path)
        if submit is not None:
            result = await _submit(hass, result, submit)
        assert result["type"] is FlowResultType.FORM, (name, result)
        forms[name] = result
        return result

    for leaf in ("outdoor", "building", "residents", "levels"):
        await render(leaf, "home_setup", leaf)
    for leaf in ("profile", "forecast", "air_quality", "cross_ventilation", "recommendation_priorities", "threshold", "model"):
        await render(leaf, "ventilation_settings", leaf)
    await render("profile_details", "ventilation_settings", "profile", submit={"operating_profile": "summer_cooling"})
    await render("threshold_percent", "ventilation_settings", "threshold", submit={"threshold_mode": "percent_total_water"})
    await render("threshold_fixed", "ventilation_settings", "threshold", submit={"threshold_mode": "fixed_ml"})
    # The ranking page is reached by choosing the room on the priorities page.
    result = await _open(hass, entry, "ventilation_settings", "recommendation_priorities")
    forms["recommendation_priority_order"] = await _submit(hass, result, {"room": "wohnzimmer"})
    for leaf in ("notifications", "energy"):
        await render(leaf, "notification_energy_settings", leaf)
    for system in ("heat_pump", "gas", "oil", "district_heating", "electric"):
        await render(f"energy_details:{system}", "notification_energy_settings", "energy", submit={"heating_system": system})
    for leaf in ("statistics", "diagnostics_sharing"):
        await render(leaf, "data_learning_settings", leaf)
    await render("add_room", "home_setup", "rooms", "add_room")
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    forms["edit_room"] = await _submit(hass, result, {"room": "wohnzimmer"})
    return forms


# --------------------------------------------------------------------------- threshold
async def test_threshold_pages_show_only_the_control_of_the_chosen_mode(hass) -> None:
    """Replaces test_threshold_detail_uses_local_mode_override_and_conditional_controls."""
    entry = _entry(rooms=[_room()], options={"threshold_mode": "fixed_ml"})
    entry.add_to_hass(hass)

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    assert _keys(result) == ["threshold_mode"]  # mode first, never both values at once
    assert _default(result, "threshold_mode") == "fixed_ml"  # opens on the stored mode

    percent = await _submit(hass, result, {"threshold_mode": "percent_total_water"})
    assert percent["step_id"] == "threshold_percent"
    assert _keys(percent) == ["min_potential_percent_total_water"]

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    fixed = await _submit(hass, result, {"threshold_mode": "fixed_ml"})
    assert fixed["step_id"] == "threshold_fixed"
    assert _keys(fixed) == ["min_potential_total_ml"]

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    adaptive = await _submit(hass, result, {"threshold_mode": "adaptive_home_size"})
    # adaptive needs no value: straight back to the menu, no value control at all
    assert adaptive["type"] is FlowResultType.MENU and adaptive["step_id"] == "ventilation_settings"


async def test_threshold_save_writes_only_the_active_value(hass) -> None:
    """Replaces test_threshold_apply_only_writes_active_value."""
    entry = _entry(
        rooms=[_room()],
        options={"threshold_mode": "adaptive_home_size", "min_potential_percent_total_water": 10.0, "min_potential_total_ml": 500.0},
    )
    entry.add_to_hass(hass)

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    result = await _submit(hass, result, {"threshold_mode": "percent_total_water"})
    await _submit(hass, result, {"min_potential_percent_total_water": 12.5})
    assert entry.options["threshold_mode"] == "percent_total_water"
    assert entry.options["min_potential_percent_total_water"] == 12.5
    assert entry.options["min_potential_total_ml"] == 500.0  # inactive value untouched

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    result = await _submit(hass, result, {"threshold_mode": "fixed_ml"})
    await _submit(hass, result, {"min_potential_total_ml": 800})
    assert entry.options["threshold_mode"] == "fixed_ml"
    assert entry.options["min_potential_total_ml"] == 800.0
    assert entry.options["min_potential_percent_total_water"] == 12.5  # inactive value untouched

    result = await _open(hass, entry, "ventilation_settings", "threshold")
    await _submit(hass, result, {"threshold_mode": "adaptive_home_size"})
    assert entry.options["threshold_mode"] == "adaptive_home_size"
    assert entry.options["min_potential_percent_total_water"] == 12.5
    assert entry.options["min_potential_total_ml"] == 800.0


# --------------------------------------------------------------------------- live apply / reload policy
async def test_runtime_option_change_is_applied_live_without_reload(hass) -> None:
    """Replaces test_020307_runtime_settings_use_lightweight_refresh."""
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _setup_entry(options=dict(DEFAULT_OPTIONS)))
    coordinator = entry.runtime_data

    with patch.object(hass.config_entries, "async_schedule_reload") as reload, patch.object(
        coordinator, "async_rebuild_listeners", wraps=coordinator.async_rebuild_listeners
    ) as rebuild, patch.object(coordinator, "async_request_refresh", wraps=coordinator.async_request_refresh) as refresh:
        result = await _open(hass, entry, "ventilation_settings", "forecast")
        result = await _submit(hass, result, {"forecast_horizon_min": 15})
        await hass.async_block_till_done()
        assert result["step_id"] == "ventilation_settings"
        reload.assert_not_called()
        refresh.assert_awaited()  # lightweight recalculation of the running coordinator
        rebuild.assert_not_called()  # no listener-relevant key changed

        result = await _open(hass, entry, "home_setup", "residents")
        await _submit(hass, result, {"residents": {"adult_occupants": 1, "child_occupants": 0, "pets_in_household": False,
                                                    "adult_presence_entities": ["person.anna"]}})
        await hass.async_block_till_done()
        rebuild.assert_awaited()  # presence entities are state listeners
        reload.assert_not_called()

    assert entry.runtime_data is coordinator  # same coordinator, nothing torn down
    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.options["forecast_horizon_min"] == 15
    await _unload(hass, entry)


async def test_only_room_topology_changes_reload_the_entry(hass) -> None:
    """Replaces test_020307_only_structural_dashboard_room_changes_keep_reload."""
    entry = _entry(rooms=[_room("A", key="a"), _room("B", key="b")], options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    entry.runtime_data = _fake_coordinator()

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        # existing-room edit (key kept): no reload
        result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
        result = await _submit(hass, result, {"room": "a"})
        result = await _submit(hass, result, _room_input("A", "a", volume=60.0))
        assert result["step_id"] == "rooms"
        # reorder: no reload
        result = await _open(hass, entry, "home_setup", "rooms", "sort_rooms")
        await _submit(hass, result, {"room_position_1": "b", "room_position_2": "a"})
        # plain option page: no reload
        result = await _open(hass, entry, "ventilation_settings", "forecast")
        await _submit(hass, result, {"forecast_horizon_min": 10})
        await hass.async_block_till_done()
        reload.assert_not_called()
        assert [r["key"] for r in entry.data["rooms"]] == ["b", "a"]
        assert entry.data["rooms"][1]["volume"] == 60.0

        # add room: structural, reload once at the end of the wizard
        result = await _open(hass, entry, "home_setup", "rooms", "add_room")
        result = await _submit(hass, result, _room_input("C", "c"))
        assert result["step_id"] == "rooms"
        reload.assert_called_once_with(entry.entry_id)

        # delete room: structural, reload
        reload.reset_mock()
        result = await _open(hass, entry, "home_setup", "rooms", "remove_room")
        await _submit(hass, result, {"room": "c", "confirm": True})
        reload.assert_called_once_with(entry.entry_id)


async def test_options_page_returns_before_the_runtime_recalculation_finishes(hass) -> None:
    """Replaces test_020307_settings_http_ack_does_not_wait_for_full_recalculation."""
    entry = _entry(rooms=[_room()], options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    coordinator = _fake_coordinator()
    release = asyncio.Event()
    finished: list[bool] = []

    async def _slow_refresh() -> None:
        await release.wait()
        finished.append(True)

    coordinator.async_request_refresh = AsyncMock(side_effect=_slow_refresh)
    entry.runtime_data = coordinator

    result = await _open(hass, entry, "ventilation_settings", "forecast")
    result = await _submit(hass, result, {"forecast_horizon_min": 20})
    # The page answered and the value is stored although the recalculation still runs.
    assert result["step_id"] == "ventilation_settings"
    assert entry.options["forecast_horizon_min"] == 20
    await asyncio.sleep(0)
    coordinator.async_request_refresh.assert_awaited()
    assert finished == []
    release.set()
    await hass.async_block_till_done()
    assert finished == [True]


async def test_existing_room_edit_is_applied_live_without_reload(hass) -> None:
    """Replaces test_dashboard_existing_room_edit_uses_live_runtime_refresh.

    Editing an existing room keeps its entities (no reload) and the running
    coordinator must pick up the new configuration, e.g. listen to a newly
    assigned opening contact.
    """
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(DOOR, "off", {"device_class": "door"})
    entry = await _setup(hass, _setup_entry())
    coordinator = entry.runtime_data
    assert DOOR not in coordinator._contact_entities

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
        result = await _submit(hass, result, {"room": "wohnzimmer"})
        assert result["step_id"] == "edit_room"
        result = await _submit(hass, result, {
            "identity": {CONF_ROOM_NAME: "Wohnzimmer", "floor": "EG", CONF_ROOM_INCLUDE_CALCULATIONS: True},
            "sensors": {
                CONF_ROOM_TEMPERATURE: ["sensor.wohnzimmer_temperature"],
                CONF_ROOM_HUMIDITY: ["sensor.wohnzimmer_humidity"],
                CONF_ROOM_CONTACTS: [WINDOW, DOOR],
                CONF_CONTACT_MODE: CONTACT_MODE_ANY,
            },
            "geometry": {"volume": 55.0},
        })
        while result["type"] is FlowResultType.FORM and result["step_id"] == "contact_references":
            result = await _submit(hass, result, {"delay_seconds": 0, "orientation": "s"})
        assert result["step_id"] == "rooms"
        await hass.async_block_till_done()
        reload.assert_not_called()

    assert entry.data["rooms"][0][CONF_ROOM_CONTACTS] == [WINDOW, DOOR]
    assert entry.runtime_data is coordinator
    assert DOOR in coordinator._contact_entities, "edited room is not applied to the running coordinator"
    await _unload(hass, entry)


# --------------------------------------------------------------------------- one settings contract
async def test_every_native_option_key_is_editable_on_a_native_form(hass) -> None:
    """Replaces test_every_native_global_option_is_exposed_by_dashboard,
    test_dashboard_settings_cover_every_native_options_key and
    test_native_and_dashboard_settings_are_contract_checked_on_both_surfaces."""
    forms = await _all_native_forms(hass)
    shown = {key for result in forms.values() for key in _keys(result)}
    # resident_room_profiles is edited through readable per-person fields and
    # stored as one compact value (see test_residents_structured_profiles).
    assert {"adult_1_rooms", "adult_1_thermal", "adult_1_notifications", "child_1_rooms"} <= shown
    missing = sorted(NATIVE_OPTION_KEYS - {"resident_room_profiles"} - shown)
    assert missing == [], f"native options without a Devices & services field: {missing}"


async def test_saving_native_pages_writes_only_contract_option_keys(hass) -> None:
    """Replaces test_dashboard_cannot_create_dashboard_only_global_options."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    # Home Assistant validates every submission against the rendered form:
    # a setting that is not on the page cannot be written.
    result = await _open(hass, entry, "ventilation_settings", "forecast")
    with pytest.raises(InvalidData):
        await _submit(hass, result, {"forecast_horizon_min": 10, "dashboard_only_option": 1})
    assert "dashboard_only_option" not in entry.options

    for path, data in (
        (("ventilation_settings", "forecast"), {"forecast_horizon_min": 10}),
        (("ventilation_settings", "air_quality"), {}),
        (("ventilation_settings", "cross_ventilation"), {}),
        (("home_setup", "building"), {}),
        (("data_learning_settings", "diagnostics_sharing"), {}),
        (("notification_energy_settings", "notifications"), {"test_notification_now": False}),
    ):
        result = await _open(hass, entry, *path)
        await _submit(hass, result, data)
    result = await _open(hass, entry, "finish")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    unknown = sorted(set(entry.options) - NATIVE_OPTION_KEYS - set(DEFAULT_OPTIONS))
    assert unknown == []
    assert "test_notification_now" not in entry.options  # form action, not a setting


async def test_no_native_form_shows_the_same_setting_twice(hass) -> None:
    """Replaces test_dashboard_settings_cover_canonical_api_without_visible_duplicate_fields."""
    forms = await _all_native_forms(hass)
    for name, result in forms.items():
        keys = _keys(result)
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        assert duplicates == [], f"{name} shows {duplicates} twice"
    # Comfort/dehumidify efficiency values live only on the model page; the
    # profile page does not open a second copy of them.
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "profile")
    result = await _submit(hass, result, {"operating_profile": "comfort"})
    assert result["type"] is FlowResultType.MENU and result["step_id"] == "ventilation_settings"


async def test_outdoor_base_data_is_edited_natively_and_stored_in_entry_data(hass) -> None:
    """Replaces test_base_data_surface_parity."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "outdoor")
    assert set(_keys(result)) == {
        CONF_OUTDOOR_WEATHER, CONF_OUTDOOR_TEMPERATURE, CONF_OUTDOOR_HUMIDITY, CONF_POLLEN_ENTITY, CONF_OUTDOOR_PM25_ENTITY,
    }
    result = await _submit(hass, result, {
        CONF_OUTDOOR_WEATHER: "weather.other",
        CONF_POLLEN_ENTITY: ["sensor.pollen_birch", "sensor.pollen_grass"],
        CONF_OUTDOOR_PM25_ENTITY: ["sensor.outdoor_pm25"],
    })
    assert result["step_id"] == "home_setup"
    assert entry.data[CONF_OUTDOOR_WEATHER] == "weather.other"
    assert entry.data[CONF_POLLEN_ENTITY] == ["sensor.pollen_birch", "sensor.pollen_grass"]
    assert entry.data[CONF_OUTDOOR_PM25_ENTITY] == ["sensor.outdoor_pm25"]
    # base data are entry data, never duplicated into the option store
    assert not {CONF_OUTDOOR_WEATHER, CONF_POLLEN_ENTITY, CONF_OUTDOOR_PM25_ENTITY} & set(entry.options)


# --------------------------------------------------------------------------- room editors
ROOM_CORE_FIELDS = {
    "name", "floor", "include_in_calculations", "temperature", "humidity", "contacts", "contact_mode",
    "volume", "length", "width", "height", "co2", "voc", "pm25", "illuminance", "climate", "exhaust_fan",
    "supply_fan", "ventilation_device", "dehumidifier", "humidifier", "air_purifier",
}


async def test_room_forms_expose_every_core_room_field(hass, fast_commit_sleep) -> None:
    """Replaces test_room_core_fields_exist_on_both_surfaces."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    add = await _open(hass, entry, "home_setup", "rooms", "add_room")
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    edit = await _submit(hass, result, {"room": "wohnzimmer"})
    create = await _start(hass, entry, "create_room")  # native room subentry
    for form in (add, edit, create):
        missing = sorted(ROOM_CORE_FIELDS - set(_keys(form)))
        assert missing == [], f"{form['step_id']} lacks {missing}"
    # the edit form is pre-filled with the stored room
    assert _default(edit, "name") == "Wohnzimmer"
    assert edit["description_placeholders"] == {"room_name": "Wohnzimmer"}


async def test_native_room_features_are_all_reachable(hass) -> None:
    """Replaces test_settings_ui_exposes_native_room_features."""
    entry = _entry(rooms=[_room(contacts=[WINDOW])])
    entry.add_to_hass(hass)
    rooms_menu = await _open(hass, entry, "home_setup", "rooms")
    assert {"add_room", "edit_room_select", "sort_rooms", "remove_room"} <= set(rooms_menu["menu_options"])
    levels = await _open(hass, entry, "home_setup", "levels")
    assert levels["step_id"] == "levels"

    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    edit = await _submit(hass, result, {"room": "wohnzimmer"})
    assert {"temperature", "humidity", "contacts", "contact_mode", "volume", "length", "width", "height", "co2",
            CONF_ROOM_MOISTURE_SOURCES} <= set(_keys(edit))
    refs = await _submit(hass, edit, _room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW], co2=False))
    assert refs["step_id"] == "contact_references"
    # per-opening reference air, orientation and delay replace the old room-wide fields
    assert {"reference_temperature", "reference_humidity", "orientation", "delay_seconds"} <= set(_keys(refs))
    assert "reference_temperature" not in _keys(edit)


async def test_room_form_offers_every_moisture_source_with_translated_labels(hass) -> None:
    """Replaces test_all_requested_moisture_sources_are_offered."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    form = await _open(hass, entry, "home_setup", "rooms", "add_room")
    picker = _field(form, CONF_ROOM_MOISTURE_SOURCES)
    assert isinstance(picker, selector.SelectSelector)
    assert picker.config["multiple"] is True
    requested = ["shower", "bath", "sauna", "cooking", "washing_machine", "dryer", "ironing_station", "laundry_drying"]
    assert list(picker.config["options"]) == requested == MOISTURE_SOURCES
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))["selector"]["moisture_source"]["options"]
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))["selector"]["moisture_source"]["options"]
    expected_de = {"shower": "Dusche", "bath": "Badewanne", "sauna": "Sauna", "cooking": "Kochen",
                   "washing_machine": "Waschmaschine", "dryer": "Trockner", "ironing_station": "Bügelstation",
                   "laundry_drying": "Wäsche aufhängen"}
    for value, label in expected_de.items():
        assert de[value].startswith(label), value
        assert en[value], value
    # a selected source is stored on the room
    result = await _submit(hass, form, {**_room_input("Bad", "bad"), "properties": {CONF_ROOM_MOISTURE_SOURCES: ["shower", "laundry_drying"]}})
    assert result["step_id"] == "rooms"
    bad = next(r for r in entry.data["rooms"] if r["key"] == "bad")
    assert bad[CONF_ROOM_MOISTURE_SOURCES] == ["shower", "laundry_drying"]


async def test_unit_based_climate_sensors_are_accepted_by_room_flow_and_runtime(hass) -> None:
    """Replaces test_dashboard_accepts_unit_based_temperature_and_humidity_sensors."""
    _set_sources(hass, "wohnzimmer")
    # sensors with a unit but without a device_class (e.g. template/MQTT sensors)
    hass.states.async_set("sensor.bad_t", "22.5", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.bad_rh", "71", {"unit_of_measurement": "%"})
    entry = await _setup(hass, _setup_entry())
    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    result = await _submit(hass, result, {
        "identity": {CONF_ROOM_NAME: "Bad", "floor": "EG", CONF_ROOM_INCLUDE_CALCULATIONS: True},
        "sensors": {CONF_ROOM_TEMPERATURE: ["sensor.bad_t"], CONF_ROOM_HUMIDITY: ["sensor.bad_rh"],
                    CONF_ROOM_CONTACTS: [], CONF_CONTACT_MODE: CONTACT_MODE_ANY},
        "geometry": {"volume": 20.0},
    })
    assert result["step_id"] == "rooms" and not result.get("errors")
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    room = coordinator.data["rooms"]["bad"]
    assert room["temperature"] == pytest.approx(22.5)
    assert room["humidity"] == pytest.approx(71)
    await _unload(hass, entry)


async def test_passage_door_belongs_to_each_single_opening(hass) -> None:
    """Replaces test_dashboard_passage_setting_is_inside_each_contact_card."""
    entry = _entry(rooms=[_room(contacts=[])])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    first = await _submit(hass, result, _room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW, DOOR]))
    assert first["step_id"] == "contact_references"
    assert first["description_placeholders"]["contact_entity"] == WINDOW
    keys = _keys(first)
    # the passage flag is part of the opening's own page, after its covers
    assert "passage_door" in keys and keys.index("passage_door") > keys.index("covers")
    second = await _submit(hass, first, {"delay_seconds": 0, "orientation": "s", "passage_door": False})
    assert second["description_placeholders"]["contact_entity"] == DOOR
    assert "passage_door" in _keys(second)
    done = await _submit(hass, second, {"delay_seconds": 0, "orientation": "w", "passage_door": True})
    assert done["step_id"] == "rooms"
    assert entry.data["rooms"][0][CONF_CONTACT_PASSAGE_DOORS] == {WINDOW: False, DOOR: True}


async def test_room_editors_never_write_legacy_room_wide_reference_air(hass, fast_commit_sleep) -> None:
    """Replaces test_current_editors_never_write_legacy_room_wide_reference_air."""
    legacy = _room(contacts=[WINDOW])
    legacy[CONF_ROOM_REFERENCE_TEMPERATURE] = "sensor.flur_temperature"
    legacy[CONF_ROOM_REFERENCE_HUMIDITY] = "sensor.flur_humidity"
    entry = _entry(rooms=[legacy])
    entry.add_to_hass(hass)

    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    result = await _submit(hass, result, _room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW]))
    result = await _submit(hass, result, {"delay_seconds": 0, "orientation": "s",
                                          "reference_temperature": "sensor.flur_temperature",
                                          "reference_humidity": "sensor.flur_humidity"})
    assert result["step_id"] == "rooms"
    room = entry.data["rooms"][0]
    assert CONF_ROOM_REFERENCE_TEMPERATURE not in room and CONF_ROOM_REFERENCE_HUMIDITY not in room
    assert room["contact_reference_temperatures"] == {WINDOW: "sensor.flur_temperature"}

    # the native room subentry editor follows the same contract
    result = await _start(hass, entry, "create_room")
    sections = _room_input("Bad", "bad")
    sections["sensors"][CONF_ROOM_REFERENCE_TEMPERATURE] = "sensor.x"
    with pytest.raises(InvalidData):  # not a field of the current editor
        await hass.config_entries.subentries.async_configure(result["flow_id"], sections)


async def test_changed_contacts_drive_the_following_opening_pages(hass) -> None:
    """Replaces test_dashboard_room_contacts_update_detail_controls_without_saving_first."""
    room = _room(contacts=[WINDOW])
    room["contact_orientations"] = {WINDOW: "n"}
    room["contact_delays"] = {WINDOW: 30}
    entry = _entry(rooms=[room])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    result = await _submit(hass, result, {"room": "wohnzimmer"})
    # replace the window by a door in the same submission: the per-opening pages
    # follow the new selection at once, no separate save is needed first
    result = await _submit(hass, result, _room_input("Wohnzimmer", "wohnzimmer", contacts=[DOOR]))
    assert result["step_id"] == "contact_references"
    assert result["description_placeholders"]["contact_entity"] == DOOR
    assert result["description_placeholders"]["contact_count"] == "1"
    result = await _submit(hass, result, {"delay_seconds": 5, "orientation": "e"})
    assert result["step_id"] == "rooms"
    stored = entry.data["rooms"][0]
    assert stored["contact_orientations"] == {DOOR: "e"}
    assert stored["contact_delays"] == {DOOR: 5}


async def test_legacy_scalar_sensor_is_preselected_in_the_multi_select(hass) -> None:
    """Replaces test_dashboard_multiselect_preserves_legacy_scalar_sensor."""
    legacy = _room()  # stores temperature/humidity as plain strings (pre-multi-sensor)
    assert isinstance(legacy[CONF_ROOM_TEMPERATURE], str)
    entry = _entry(rooms=[legacy])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    edit = await _submit(hass, result, {"room": "wohnzimmer"})
    picker = _field(edit, CONF_ROOM_TEMPERATURE)
    assert picker.config["multiple"] is True
    sensors_section = next(v for m, v in edit["data_schema"].schema.items() if str(m) == "sensors")
    markers = {str(m): m for m in sensors_section.schema.schema}
    suggested = (markers[CONF_ROOM_TEMPERATURE].description or {}).get("suggested_value")
    assert suggested == ["sensor.wohnzimmer_temperature"]
    assert (markers[CONF_ROOM_HUMIDITY].description or {}).get("suggested_value") == ["sensor.wohnzimmer_humidity"]


async def test_contact_picker_offers_real_and_helper_three_state_sources(hass) -> None:
    """Replaces test_room_editor_search_filtered_contacts_and_laundry and
    test_real_and_helper_three_state_are_selectable_on_both_surfaces."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    add = await _open(hass, entry, "home_setup", "rooms", "add_room")
    create_flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"), context={"source": config_entries.SOURCE_USER}
    )
    create = await hass.config_entries.subentries.async_configure(create_flow["flow_id"], {"next_step_id": "create_room"})
    for form in (add, create):
        picker = _field(form, CONF_ROOM_CONTACTS)
        assert isinstance(picker, selector.EntitySelector)  # HA's searchable entity picker
        domains = set(picker.config["domain"])
        assert domains == {"binary_sensor", "sensor", "input_select", "select"}
        assert picker.config["multiple"] is True
        assert "laundry_drying" in _field(form, CONF_ROOM_MOISTURE_SOURCES).config["options"]


async def test_every_room_entity_field_uses_the_ha_entity_picker(hass) -> None:
    """Replaces test_dashboard_entity_selection_uses_integrated_ha_search_picker."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    form = await _open(hass, entry, "home_setup", "rooms", "add_room")
    entity_fields = {"temperature", "humidity", "contacts", "co2", "voc", "pm25", "illuminance", "climate",
                     "exhaust_fan", "supply_fan", "ventilation_device", "dehumidifier", "humidifier", "air_purifier"}
    for key in entity_fields:
        assert isinstance(_field(form, key), selector.EntitySelector), key
    # no free-text entity id input anywhere on the room form
    text_fields = [key for _s, key, value in _schema_fields(form["data_schema"]) if isinstance(value, selector.TextSelector)]
    assert text_fields == ["name"]


async def test_room_form_has_goal_ranking_target_temperature_and_mechanical_ventilation(hass) -> None:
    """Replaces test_dashboard_has_goal_tracker_and_all_room_edit_fields (room-edit half)."""
    entry = _entry(rooms=[_rich_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "home_setup", "rooms", "edit_room_select")
    edit = await _submit(hass, result, {"room": "wohnzimmer"})
    for key in ("target_temperature_mode", "target_temperature", "target_temperature_fallback", "exhaust_fan"):
        assert key in _keys(edit), key
    assert list(_field(edit, "target_temperature_mode").config["options"]) == ["automatic", "manual"]
    data = _room_input("Wohnzimmer", "wohnzimmer", contacts=[WINDOW], co2=True)
    data["sensors"].update({"target_temperature_mode": "manual", "target_temperature": 21.0,
                            "target_temperature_fallback": 20.0, "exhaust_fan": ["fan.bad"]})
    goals = await _submit(hass, edit, data)
    assert goals["step_id"] == "room_goals"
    assert [k for k in _keys(goals) if k.startswith("goal_priority_")] == ["goal_priority_1", "goal_priority_2", "goal_priority_3"]
    refs = await _submit(hass, goals, {"goal_priority_1": "co2", "goal_priority_2": "humidity", "goal_priority_3": "temperature"})
    assert refs["step_id"] == "contact_references"
    await _submit(hass, refs, {"delay_seconds": 0, "orientation": "s"})
    room = entry.data["rooms"][0]
    assert room["goal_priorities"] == ["co2", "humidity", "temperature"]
    assert room["target_temperature_mode"] == "manual" and room["target_temperature_fallback"] == 20.0
    assert room["exhaust_fan"] == ["fan.bad"]


# --------------------------------------------------------------------------- residents / notifications / navigation
async def test_resident_room_selection_is_multi_select_and_reopens_with_saved_rooms(hass) -> None:
    """Replaces test_resident_multiselect_is_explicit_and_stateful."""
    entry = _entry(rooms=[_room(), _room("Bad", key="bad")], options={"adult_occupants": 1, "adult_resident_names": "Anna"})
    entry.add_to_hass(hass)
    form = await _open(hass, entry, "home_setup", "residents")
    picker = _field(form, "adult_1_rooms")
    assert picker.config["multiple"] is True
    assert [o["value"] for o in picker.config["options"]] == ["wohnzimmer", "bad"]
    await _submit(hass, form, {
        "residents": {"adult_occupants": 1, "adult_resident_names": "Anna", "child_occupants": 0, "pets_in_household": False},
        "resident_profiles": {"adult_1_rooms": ["bad", "wohnzimmer"], "adult_1_thermal": "cool"},
    })
    assert json.loads(entry.options["resident_room_profiles"])["adult:0"]["room_keys"] == ["bad", "wohnzimmer"]
    reopened = await _open(hass, entry, "home_setup", "residents")
    assert _default(reopened, "adult_1_rooms") == ["bad", "wohnzimmer"]
    assert _default(reopened, "adult_1_thermal") == "cool"


async def test_notification_targets_and_test_send_cover_services_and_notify_entities(hass) -> None:
    """Replaces test_dashboard_and_native_flow_share_same_backend_discovery and
    test_notification_test_button_remains_available."""
    legacy_calls = async_mock_service(hass, "notify", "phone")
    entity_calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set("notify.kitchen_display", "unknown")
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    form = await _open(hass, entry, "notification_energy_settings", "notifications")
    values = {o["value"] for o in _field(form, "notification_targets").config["options"]}
    assert "phone" in values  # legacy notify service
    assert "entity:notify.kitchen_display" in values  # modern notify entity
    assert "send_message" not in values  # the generic action itself is no target
    assert "test_notification_now" in _keys(form)

    result = await _submit(hass, form, {"notification_targets": ["entity:notify.kitchen_display"], "test_notification_now": True})
    await hass.async_block_till_done()
    assert result["step_id"] == "notifications" and not result.get("errors")
    assert len(entity_calls) == 1
    assert entity_calls[0].data.get("entity_id") in ("notify.kitchen_display", ["notify.kitchen_display"])
    result = await _submit(hass, result, {"notification_targets": ["phone"], "test_notification_now": True})
    await hass.async_block_till_done()
    assert len(legacy_calls) == 1


async def test_legacy_routes_redirect_and_every_settings_section_has_an_icon(hass) -> None:
    """Replaces test_settings_navigation_has_icons_and_legacy_duplicate_routes_redirect."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    flow = _flow(hass, await _open(hass, entry))
    # former duplicate forms are never shown again; they lead to the canonical pages
    assert (await flow.async_step_house())["step_id"] == "home_setup"
    assert (await flow.async_step_personalisation())["step_id"] == "residents"

    icons = json.loads((COMP / "icons.json").read_text(encoding="utf-8"))["options"]["step"]
    forms = await _all_native_forms(hass)
    sectioned = {}
    for result in forms.values():
        names = {sec for sec, _key, _value in _schema_fields(result["data_schema"]) if sec}
        if names:
            sectioned[result["step_id"]] = names
    assert {"add_room", "edit_room", "model", "residents"} <= set(sectioned)
    for step_id, names in sectioned.items():
        declared = (icons.get(step_id) or {}).get("sections") or {}
        missing = sorted(names - set(declared))
        assert missing == [], f"{step_id} sections without icon: {missing}"
        assert all(str(icon).startswith("mdi:") for icon in declared.values())
