"""0.26.5.4 (community, HarryP): exchanged air share during a real airing – display only.

The share and the time to 95 % reach the dashboard (coordinator data / live
channel); the room entities do not carry them, so the recorder does not write
a row every cycle. Nothing else changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.helpers import entity_registry as er

from custom_components.freshairiq.const import DOMAIN
from ha_tests.test_cov_setup_and_platforms import _entry, _set_sources, _setup, _unload


async def test_the_dashboard_shows_the_exchanged_share_while_airing(hass, freezer) -> None:
    freezer.move_to(datetime(2026, 10, 25, 7, 0, tzinfo=timezone.utc))
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    assert coordinator.data["rooms"]["wohnzimmer"]["air_exchange"] is None  # nothing while no airing runs
    hass.states.async_set("binary_sensor.wohnzimmer_window", "on")
    seen = []
    for _ in range(8):
        freezer.tick(timedelta(minutes=1))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        seen.append(coordinator.data["rooms"]["wohnzimmer"]["air_exchange"])
    running = [value for value in seen if value]
    assert len(running) >= 6
    percents = [value["exchanged_percent"] for value in running]
    assert percents == sorted(percents) and percents[-1] > percents[0]
    minutes = [value["minutes_to_95"] for value in running]
    assert minutes == sorted(minutes, reverse=True) and minutes[-1] > 0
    assert running[-1]["estimate"] is True  # nothing learned yet in this room
    action_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_wohnzimmer_action")
    assert "air_exchange" not in hass.states.get(action_id).attributes["freshairiq_room_payload"]
    hass.states.async_set("binary_sensor.wohnzimmer_window", "off")
    for _ in range(3):
        freezer.tick(timedelta(seconds=20))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert coordinator.data["rooms"]["wohnzimmer"]["air_exchange"] is None
    await _unload(hass, entry)
