"""Additional real-Home-Assistant coverage for FreshAirIQ flows.

These tests deliberately exercise recovery paths rather than adding new flow
behaviour. Home Assistant's quality scale requires the config, reconfigure and
options flows to recover from invalid user input.
"""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq.config_flow import _contact_reference_field
from custom_components.freshairiq.const import (
    CONF_CONTACT_MODE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOLUME,
    DEFAULT_OPTIONS,
    DOMAIN,
    LEGACY_DOMAIN,
    CONTACT_MODE_ANY,
)


async def _start_room_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_WEATHER: "weather.home"}
    )


async def test_contact_reference_pair_error_recovers(hass) -> None:
    """A partial per-opening reference pair must be correctable in-place."""
    result = await _start_room_flow(hass)
    assert result["step_id"] == "room"

    contact = "binary_sensor.office_window"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_NAME: "Arbeitszimmer",
            CONF_ROOM_TEMPERATURE: "sensor.office_temperature",
            CONF_ROOM_HUMIDITY: "sensor.office_humidity",
            CONF_ROOM_CONTACTS: [contact],
            CONF_CONTACT_MODE: CONTACT_MODE_ANY,
            CONF_ROOM_VOLUME: 35.0,
        },
    )
    assert result["step_id"] == "room_orientations"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {contact: "e"}
    )
    assert result["step_id"] == "room_references"

    temp_key = _contact_reference_field(contact, "temperature")
    humidity_key = _contact_reference_field(contact, "humidity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {temp_key: "sensor.conservatory_temperature"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "room_references"
    assert result["errors"]["base"] == "contact_reference_pair_required"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            temp_key: "sensor.conservatory_temperature",
            humidity_key: "sensor.conservatory_humidity",
        },
    )
    assert result["step_id"] == "more_rooms"


async def test_legacy_import_can_be_declined_and_recover_to_normal_setup(hass) -> None:
    """Declining legacy import must leave a usable normal setup form."""
    legacy = MockConfigEntry(
        domain=LEGACY_DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.legacy", "rooms": []},
    )
    legacy.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy_import"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"import_legacy": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_WEATHER: "weather.new"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "room"


async def test_legacy_import_creates_freshairiq_entry(hass) -> None:
    """Accepting legacy import migrates the data without deleting the source entry."""
    legacy = MockConfigEntry(
        domain=LEGACY_DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.legacy", "rooms": []},
    )
    legacy.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"import_legacy": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FreshAirIQ"
    assert result["data"][CONF_OUTDOOR_WEATHER] == "weather.legacy"
    assert result["data"]["legacy_entry_id"] == legacy.entry_id


async def test_options_outdoor_error_recovers_and_persists(hass) -> None:
    """Options outdoor page validates partial pairs and persists a corrected source."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.old", "rooms": [], "levels": []},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "home_setup"}
    )
    assert result["step_id"] == "home_setup"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "outdoor"}
    )
    assert result["step_id"] == "outdoor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "outdoor"
    assert result["errors"]["base"] == "outdoor_source_required"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature",
            CONF_OUTDOOR_HUMIDITY: "sensor.outdoor_humidity",
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "home_setup"
    assert entry.data.get(CONF_OUTDOOR_WEATHER) is None
    assert entry.data[CONF_OUTDOOR_TEMPERATURE] == "sensor.outdoor_temperature"
    assert entry.data[CONF_OUTDOOR_HUMIDITY] == "sensor.outdoor_humidity"


async def test_options_statistics_and_reset_defaults_persist(hass) -> None:
    """Non-structural options save immediately and reset defaults remains usable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.home", "rooms": [], "levels": []},
        options={"statistics_days": 7, "start_rh": 65.0},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "data_learning_settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "statistics"}
    )
    assert result["step_id"] == "statistics"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"statistics_days": 30}
    )
    assert result["step_id"] == "data_learning_settings"
    assert entry.options["statistics_days"] == 30

    # A new options flow verifies persistence rather than relying on working-copy state.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "maintenance"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset_defaults"}
    )
    assert result["step_id"] == "reset_defaults"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm": True}
    )
    assert result["step_id"] == "maintenance"
    assert entry.options["start_rh"] == DEFAULT_OPTIONS["start_rh"]
    assert entry.options["statistics_days"] == DEFAULT_OPTIONS["statistics_days"]
