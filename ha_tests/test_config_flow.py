"""Real Home Assistant config-flow tests for FreshAirIQ."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    CONTACT_MODE_ANY,
    DOMAIN,
)


async def test_user_flow_requires_complete_outdoor_source(hass) -> None:
    """The first setup page rejects partial outdoor sensor pairs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "outdoor_pair_required"


async def test_user_flow_creates_entry_without_forcing_room_setup(hass) -> None:
    """FreshAirIQ is installable immediately; rooms can be added afterwards."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_WEATHER: "weather.home"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FreshAirIQ"
    assert result["data"][CONF_OUTDOOR_WEATHER] == "weather.home"
    assert result["data"]["rooms"] == []


async def test_user_flow_can_create_completely_empty_entry(hass) -> None:
    """Even the outdoor source may be configured later from either settings UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["rooms"] == []
    assert result["data"]["levels"] == []


async def test_duplicate_config_entry_is_blocked(hass) -> None:
    """FreshAirIQ is a single-house integration and must not be added twice."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={CONF_OUTDOOR_WEATHER: "weather.home"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] in {"already_configured", "single_instance_allowed"}


async def test_reconfigure_outdoor_source_validates_and_updates(hass) -> None:
    """The native reconfigure flow updates setup data without creating a new entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={CONF_OUTDOOR_WEATHER: "weather.old", "rooms": [], "levels": []},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "outdoor_pair_required"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_OUTDOOR_TEMPERATURE: "sensor.outdoor_temperature",
            CONF_OUTDOOR_HUMIDITY: "sensor.outdoor_humidity",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_OUTDOOR_TEMPERATURE] == "sensor.outdoor_temperature"
    assert entry.data[CONF_OUTDOOR_HUMIDITY] == "sensor.outdoor_humidity"
    assert entry.data.get(CONF_OUTDOOR_WEATHER) is None
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
