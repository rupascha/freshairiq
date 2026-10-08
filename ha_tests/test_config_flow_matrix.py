"""Broader real-Home-Assistant flow surface coverage for FreshAirIQ.

The tests in this module intentionally focus on exercising the existing flow
contract. They do not introduce new configuration behaviour.
"""
from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq.const import (
    CONF_CONTACT_MODE,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    CONTACT_MODE_ANY,
    DOMAIN,
)


def _room(name: str = "Wohnzimmer", *, key: str = "wohnzimmer") -> dict:
    """Return a representative persisted room row."""
    return {
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_TEMPERATURE: f"sensor.{key}_temperature",
        CONF_ROOM_HUMIDITY: f"sensor.{key}_humidity",
        CONF_ROOM_CONTACTS: [f"binary_sensor.{key}_window"],
        CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        CONF_ROOM_VOLUME: 55.0,
        CONF_ROOM_FLOOR: "EG",
        CONF_ROOM_INCLUDE_CALCULATIONS: True,
    }


def _entry(*, rooms: list[dict] | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            CONF_OUTDOOR_WEATHER: "weather.home",
            "rooms": list(rooms or []),
            "levels": ["EG"],
        },
        options={},
    )


async def _open_options_path(hass, entry: MockConfigEntry, *steps: str):
    """Open a fresh options flow and navigate through menu steps."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    for step in steps:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": step}
        )
    return result


@pytest.mark.parametrize(
    ("section", "expected_options"),
    [
        ("home_setup", {"outdoor", "building", "residents", "levels", "rooms", "back_to_main"}),
        ("ventilation_settings", {"profile", "forecast", "air_quality", "cross_ventilation", "model", "back_to_main"}),
        ("notification_energy_settings", {"notifications", "energy", "back_to_main"}),
        ("data_learning_settings", {"statistics", "back_to_main"}),
        ("maintenance", {"reset_learning", "reset_defaults", "back_to_main"}),
    ],
)
async def test_options_main_sections_are_reachable(
    hass, section: str, expected_options: set[str]
) -> None:
    """Every top-level options section opens as a usable HA menu."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await _open_options_path(hass, entry, section)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == section
    assert set(result["menu_options"]) == expected_options


@pytest.mark.parametrize(
    ("section", "leaf"),
    [
        ("home_setup", "outdoor"),
        ("home_setup", "building"),
        ("home_setup", "residents"),
        ("home_setup", "levels"),
        ("ventilation_settings", "profile"),
        ("ventilation_settings", "forecast"),
        ("ventilation_settings", "air_quality"),
        ("ventilation_settings", "cross_ventilation"),
        ("ventilation_settings", "model"),
        ("notification_energy_settings", "notifications"),
        ("notification_energy_settings", "energy"),
        ("data_learning_settings", "statistics"),
        ("maintenance", "reset_learning"),
        ("maintenance", "reset_defaults"),
    ],
)
async def test_options_leaf_pages_render_without_configuration_errors(
    hass, section: str, leaf: str
) -> None:
    """All user-visible option leaves can render from persisted data."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await _open_options_path(hass, entry, section, leaf)

    assert result["type"] in {FlowResultType.FORM, FlowResultType.MENU}
    assert result["step_id"] == leaf
    if result["type"] is FlowResultType.FORM:
        assert result.get("errors", {}) == {}


async def test_options_rooms_menu_exposes_structural_actions(hass) -> None:
    """Room management exposes add/sort/remove only when rooms exist."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await _open_options_path(hass, entry, "home_setup", "rooms")

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "rooms"
    assert set(result["menu_options"]) == {
        "add_room",
        "edit_room_select",
        "sort_rooms",
        "remove_room",
        "back_to_home_setup",
    }


async def test_options_empty_rooms_menu_only_offers_add(hass) -> None:
    """Empty installations must not expose impossible sort/remove actions."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _open_options_path(hass, entry, "home_setup", "rooms")

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "rooms"
    assert set(result["menu_options"]) == {"add_room", "back_to_home_setup"}


async def test_native_room_subentry_can_add_room_without_contacts(hass) -> None:
    """A native room subentry can create a simple sensor-only room."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_NAME: "Schlafzimmer",
            CONF_ROOM_TEMPERATURE: "sensor.schlafzimmer_temperature",
            CONF_ROOM_HUMIDITY: "sensor.schlafzimmer_humidity",
            CONF_ROOM_CONTACTS: [],
            CONF_CONTACT_MODE: CONTACT_MODE_ANY,
            CONF_ROOM_VOLUME: 42.0,
            CONF_ROOM_FLOOR: "EG",
            CONF_ROOM_INCLUDE_CALCULATIONS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schlafzimmer"
    assert result["data"][CONF_ROOM_NAME] == "Schlafzimmer"
    assert entry.data["rooms"][0][CONF_ROOM_NAME] == "Schlafzimmer"


async def test_native_room_subentry_duplicate_name_recovers(hass) -> None:
    """Duplicate room validation remains correctable in the same subentry flow."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_NAME: "Wohnzimmer",
            CONF_ROOM_TEMPERATURE: "sensor.other_temperature",
            CONF_ROOM_HUMIDITY: "sensor.other_humidity",
            CONF_ROOM_CONTACTS: [],
            CONF_CONTACT_MODE: CONTACT_MODE_ANY,
            CONF_ROOM_VOLUME: 30.0,
            CONF_ROOM_FLOOR: "EG",
            CONF_ROOM_INCLUDE_CALCULATIONS: True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_NAME: "Büro",
            CONF_ROOM_TEMPERATURE: "sensor.office_temperature",
            CONF_ROOM_HUMIDITY: "sensor.office_humidity",
            CONF_ROOM_CONTACTS: [],
            CONF_CONTACT_MODE: CONTACT_MODE_ANY,
            CONF_ROOM_VOLUME: 30.0,
            CONF_ROOM_FLOOR: "EG",
            CONF_ROOM_INCLUDE_CALCULATIONS: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Büro"
