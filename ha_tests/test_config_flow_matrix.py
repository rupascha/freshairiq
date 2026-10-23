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
        ("home_setup", {"outdoor", "building", "residents", "levels", "rooms", "open_connections", "back_to_main"}),
        ("ventilation_settings", {"profile", "recommendation_priorities", "threshold", "forecast", "air_quality", "cross_ventilation", "model", "back_to_main"}),
        ("notification_energy_settings", {"notifications", "energy", "back_to_main"}),
        ("data_learning_settings", {"statistics", "diagnostics_sharing", "back_to_main"}),
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
        # Home Assistant 2026.x reports a form without errors as ``errors=None``.
        assert not result.get("errors")


async def test_options_rooms_menu_exposes_structural_actions(hass) -> None:
    """Room management exposes add/sort/remove only when rooms exist."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await _open_options_path(hass, entry, "home_setup", "rooms")

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "rooms"
    assert set(result["menu_options"]) == {
        "add_room",
        "import_ha_rooms",
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
    assert set(result["menu_options"]) == {"add_room", "import_ha_rooms", "back_to_home_setup"}


def _room_sections(name: str, prefix: str, volume: float) -> dict:
    """Input of the sectioned quick-add room form (identity/sensors/geometry)."""
    return {
        "identity": {CONF_ROOM_NAME: name, CONF_ROOM_FLOOR: "EG", CONF_ROOM_INCLUDE_CALCULATIONS: True},
        "sensors": {
            CONF_ROOM_TEMPERATURE: [f"sensor.{prefix}_temperature"],
            CONF_ROOM_HUMIDITY: [f"sensor.{prefix}_humidity"],
            CONF_ROOM_CONTACTS: [],
            CONF_CONTACT_MODE: CONTACT_MODE_ANY,
        },
        "geometry": {CONF_ROOM_VOLUME: volume},
    }


async def _open_create_room(hass, entry: MockConfigEntry):
    """The native room flow starts with a menu: create manually or import from HA."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {"create_room", "import_ha_room"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "create_room"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "create_room"
    return result


async def test_native_room_subentry_can_add_room_without_contacts(hass) -> None:
    """A native room subentry can create a simple sensor-only room."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await _open_create_room(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _room_sections("Schlafzimmer", "schlafzimmer", 42.0)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Schlafzimmer"
    assert result["data"][CONF_ROOM_NAME] == "Schlafzimmer"
    await hass.async_block_till_done()  # the room list is synchronised by the entry update listener
    assert entry.data["rooms"][0][CONF_ROOM_NAME] == "Schlafzimmer"


async def test_native_room_subentry_validation_error_recovers(hass) -> None:
    """Validation errors stay correctable in the same subentry flow; a duplicate
    room name is accepted with a unique key (behaviour since the first release)."""
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)

    result = await _open_create_room(hass, entry)
    missing_volume = _room_sections("Wohnzimmer", "other", 30.0)
    missing_volume["geometry"] = {}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], missing_volume)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "create_room"
    assert result["errors"] == {"base": "room_volume_required"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _room_sections("Wohnzimmer", "other", 30.0)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wohnzimmer"
    await hass.async_block_till_done()
    keys = [room["key"] for room in entry.data["rooms"]]
    assert keys == ["wohnzimmer", "wohnzimmer_2"]
