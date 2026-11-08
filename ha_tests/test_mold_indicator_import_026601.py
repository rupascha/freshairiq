"""v0.26.6.1 (#21): importing a Home Assistant area suggests its Mold Indicator for the surface RH – never as the
room humidity – in the options flow and in the room subentry flow."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er

from custom_components.freshairiq.const import CONF_ROOM_HUMIDITY, CONF_ROOM_MOLD_INDICATOR
from ha_tests import test_cov_options_flow as opt
from ha_tests import test_cov_room_subentry_flow as sub


def _area_with_helper(hass):
    area = ar.async_get(hass).async_create("Dachzimmer")
    registry = er.async_get(hass)
    humidity = registry.async_get_or_create("sensor", "test", "dach_rh", suggested_object_id="dach_rh")
    helper = registry.async_get_or_create("sensor", "mold_indicator", "dach_mold", suggested_object_id="dach_schimmel")
    for entity in (humidity, helper):
        registry.async_update_entity(entity.entity_id, area_id=area.id)
        hass.states.async_set(entity.entity_id, "70", {"device_class": "humidity", "unit_of_measurement": "%"})
    return area.id, humidity.entity_id, helper.entity_id


async def test_options_flow_area_import_suggests_the_helper_for_the_surface(hass) -> None:
    entry = opt._entry(rooms=[opt._room()])
    entry.add_to_hass(hass)
    area, humidity, helper = _area_with_helper(hass)
    result = await opt._open(hass, entry, "home_setup", "rooms", "import_ha_rooms")
    _choices, defaults = opt._flow(hass, result)._ha_area_options()
    assert defaults[area][CONF_ROOM_MOLD_INDICATOR] == helper
    assert defaults[area][CONF_ROOM_HUMIDITY] == [humidity]          # the helper is not offered as room humidity


async def test_room_subentry_area_import_suggests_the_helper_for_the_surface(hass) -> None:
    entry = sub._entry()
    entry.add_to_hass(hass)
    area, humidity, helper = _area_with_helper(hass)
    _choices, defaults = sub._bound_flow(hass, entry, source=config_entries.SOURCE_USER)._quick_ha_area_defaults()
    assert defaults[area][CONF_ROOM_MOLD_INDICATOR] == helper
    assert defaults[area][CONF_ROOM_HUMIDITY] == [humidity]
