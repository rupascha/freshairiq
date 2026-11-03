"""Hotfix 0.26.6.0 (9) F04 through Home Assistant: a weather entity with a wind direction but no usable speed.

The house map's live channel publishes the direction but ``available = False`` with ``reason = "no_speed"``; the
airflow model stays topological (no facade pressure, no directed cross flow) – so the dashboard draws no wind and no
inlet. A missing speed and an unsupported speed unit behave alike; a valid speed makes the wind available again.
Real Home Assistant, websocket subscription.
"""
from __future__ import annotations

import asyncio

from custom_components.freshairiq import house_map
from custom_components.freshairiq.const import CONF_OUTDOOR_WEATHER
from ha_tests.test_cov_setup_and_platforms import _set_sources, _setup, _unload
from ha_tests.test_house_map_026504 import _call, _house_entry


async def test_wind_without_a_usable_speed_is_not_shown(hass, hass_ws_client) -> None:
    _set_sources(hass, "bad", "flur")
    hass.states.async_set("weather.home", "windy", {"wind_bearing": "NW", "wind_speed_unit": "km/h"})   # no speed
    entry = await _setup(hass, _house_entry())
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_OUTDOOR_WEATHER: "weather.home"})
    client = await hass_ws_client(hass)
    proposal = (await _call(client, 1, type=house_map.PROPOSE))["result"]["layout"]
    proposal["building"]["north_confirmed"] = True
    assert (await _call(client, 2, type=house_map.SAVE, layout=proposal, base_revision=0))["success"]
    await client.send_json({"id": 3, "type": house_map.SUBSCRIBE, "entry_id": entry.entry_id})
    assert (await client.receive_json())["success"] is True
    wind = (await client.receive_json())["event"]["wind"]
    assert (wind["available"], wind["reason"], wind["from_deg"], wind["speed_ms"], wind["calm"]) == (False, "no_speed", 315.0, None, False)

    hass.states.async_set("weather.home", "windy", {"wind_bearing": "NW", "wind_speed": 18, "wind_speed_unit": "furlong/fortnight"})
    await hass.async_block_till_done()
    entry.runtime_data.async_update_listeners()
    event = (await asyncio.wait_for(client.receive_json(), 2))["event"]
    assert (event["wind"]["available"], event["wind"]["reason"]) == (False, "no_speed")
    assert event["airflow"]["model_level"] == "topology_only"

    hass.states.async_set("weather.home", "windy", {"wind_bearing": "NW", "wind_speed": 18, "wind_speed_unit": "km/h"})
    await hass.async_block_till_done()
    entry.runtime_data.async_update_listeners()
    event = (await asyncio.wait_for(client.receive_json(), 2))["event"]
    assert (event["wind"]["available"], event["wind"]["speed_ms"]) == (True, 5.0)
    await _unload(hass, entry)
