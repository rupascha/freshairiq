"""0.26.5.3 (community: recorder load): fewer recorder rows without losing anything.

* the dashboard state travels over the live channel ``freshairiq/dashboard/subscribe``;
  the status sensor keeps a small, stable summary;
* the room payload on the room action entity carries report times instead of
  counters that grew every cycle, so the entity changes only with real news;
* outside an active moisture source its detector values are held;
* clock-driven or flickering sensors publish in steps (overnight forecast 50 mL,
  today's balance 10 mL, forecast temperature change with a 0.2 °C deadband).
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.freshairiq.const import DOMAIN
from custom_components.freshairiq.dashboard_live import live_signal
from custom_components.freshairiq.dashboard_transport import SOURCE_DETAIL_KEYS, VOLATILE_ROOM_KEYS
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload

SUMMARY = {"status", "status_text", "freshairiq_transport", "freshairiq_live_api", "freshairiq_details_api",
           "freshairiq_entry_id", "freshairiq_version", "output_language", "version"}


def _id(hass, entry, key: str, domain: str = "sensor") -> str:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}")


async def _no_message(client) -> bool:
    try:
        await asyncio.wait_for(client.receive_json(), 0.2)
    except TimeoutError:
        return True
    return False


async def test_the_dashboard_state_travels_over_the_live_channel(hass, hass_ws_client) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    status = hass.states.get(_id(hass, entry, "status"))
    assert set(status.attributes) - {"friendly_name", "icon"} == SUMMARY
    assert status.attributes["freshairiq_live_api"] == "dashboard_ws_v1"

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "freshairiq/dashboard/subscribe"})
    assert (await client.receive_json())["success"] is True
    event = (await client.receive_json())["event"]
    assert event["freshairiq_entry_id"] == entry.entry_id and event["freshairiq_live_api"] == "dashboard_ws_v1"
    assert "wohnzimmer" in event["rooms"] and "intelligent_recommendation" in event and "history_14d" in event
    assert "temperature_history_14d" not in event["rooms"]["wohnzimmer"]  # charts stay on demand

    coordinator.async_update_listeners()  # same data: nothing is sent again
    assert await _no_message(client)
    coordinator.async_set_updated_data({**coordinator.data, "status_text": "geändert"})
    assert (await client.receive_json())["event"]["status_text"] == "geändert"

    await client.send_json({"id": 2, "type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"] is True
    coordinator.async_set_updated_data({**coordinator.data, "status_text": "danach"})
    assert await _no_message(client)

    await client.send_json({"id": 3, "type": "freshairiq/dashboard/subscribe", "entry_id": entry.entry_id})
    assert (await client.receive_json())["success"] is True
    assert (await client.receive_json())["event"]["status_text"] == "danach"
    await client.send_json({"id": 4, "type": "freshairiq/dashboard/subscribe", "entry_id": "unknown"})
    reply = await client.receive_json()
    assert reply["success"] is False and reply["error"]["code"] == "not_loaded"

    # a reload (e.g. a saved setting) keeps the open dashboard live: subscription 3 follows the entry
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data is not coordinator
    entry.runtime_data.async_set_updated_data({**entry.runtime_data.data, "status_text": "nach dem Neuladen"})
    texts = []
    while not texts or texts[-1] != "nach dem Neuladen":
        texts.append((await asyncio.wait_for(client.receive_json(), 2))["event"]["status_text"])
    await _unload(hass, entry)
    await asyncio.sleep(0.2)
    while not await _no_message(client):  # drain what was still on its way
        pass
    async_dispatcher_send(hass, live_signal(entry.entry_id))  # nothing is served for an unloaded entry
    assert await _no_message(client)
    entry.runtime_data = coordinator  # a stale object must not be served after the unload
    coordinator.data = None
    await client.send_json({"id": 5, "type": "freshairiq/dashboard/subscribe"})
    reply = await client.receive_json()
    while reply["id"] != 5:  # events of subscription 3 that were still on their way
        reply = await client.receive_json()
    assert reply["error"]["code"] == "not_loaded"


async def test_room_and_status_entities_do_not_change_without_news(hass, freezer) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    action_id, status_id = _id(hass, entry, "wohnzimmer_action"), _id(hass, entry, "status")
    payload = hass.states.get(action_id).attributes["freshairiq_room_payload"]
    assert not set(VOLATILE_ROOM_KEYS) & set(payload)
    assert payload["frame_temp_reported_at"] and payload["measurement_frame_oldest_at"]
    assert payload["last_measurement_at"] == max(payload["frame_temp_reported_at"], payload["frame_humidity_reported_at"])
    assert coordinator.data["rooms"]["wohnzimmer"]["frame_age_temp_s"] is not None  # internally unchanged
    for _ in range(2):  # settle (first cycles still learn the baseline)
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    before = {eid: hass.states.get(eid) for eid in (action_id, status_id)}
    for _ in range(4):
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    after = {eid: hass.states.get(eid) for eid in (action_id, status_id)}
    for eid in before:
        assert after[eid].last_changed == before[eid].last_changed
        assert after[eid].last_updated == before[eid].last_updated, eid  # no new state -> no recorder row
    await _unload(hass, entry)


async def test_moisture_source_details_are_held_while_no_source_is_active(hass) -> None:
    _set_sources(hass, "bad")
    room = {**_room("bad", "Bad"), "moisture_sources": ["shower"]}
    entry = await _setup(hass, _entry(rooms=[room]))
    coordinator = entry.runtime_data
    source_id, action_id = _id(hass, entry, "bad_moisture_source", "binary_sensor"), _id(hass, entry, "bad_action")

    def publish(**values) -> None:
        coordinator.data["rooms"]["bad"].update(values)
        coordinator.async_update_listeners()

    publish(moisture_source_active=False, moisture_source_recovery=False, moisture_source_rate_ml_min=3.1, moisture_source_generated_ml_window=12)
    await hass.async_block_till_done()
    attrs = hass.states.get(source_id).attributes
    assert (attrs["rate_ml_min"], attrs["generated_ml"], attrs["confidence"], attrs["source"]) == (None, None, 0, None)
    assert all(hass.states.get(action_id).attributes["freshairiq_room_payload"][key] is None for key in SOURCE_DETAIL_KEYS)

    publish(moisture_source_active=True, moisture_source_identified_source="shower", moisture_source_confidence=90,
            moisture_source_rate_ml_min=25.0, moisture_source_generated_ml_window=140, moisture_source_ah_rise_g_m3=1.2)
    await hass.async_block_till_done()
    assert hass.states.get(source_id).attributes["rate_ml_min"] == 25.0
    assert hass.states.get(action_id).attributes["freshairiq_room_payload"]["moisture_source_ah_rise_g_m3"] == 1.2

    publish(moisture_source_active=False, moisture_source_rate_ml_min=0.4, moisture_source_generated_ml_window=3, moisture_source_ah_rise_g_m3=0.1)
    await hass.async_block_till_done()
    attrs = hass.states.get(source_id).attributes
    assert hass.states.get(source_id).state == "off"
    assert (attrs["rate_ml_min"], attrs["generated_ml"], attrs["source"], attrs["confidence"]) == (25.0, 140, "shower", 90)
    held = hass.states.get(action_id).attributes["freshairiq_room_payload"]
    assert (held["moisture_source_rate_ml_min"], held["moisture_source_ah_rise_g_m3"]) == (25.0, 1.2)
    publish(moisture_source_recovery=True)  # recovery shows the live values again
    await hass.async_block_till_done()
    assert hass.states.get(source_id).attributes["rate_ml_min"] == 0.4
    await _unload(hass, entry)


@pytest.mark.parametrize(("key", "values", "expected"), [
    ("overnight_forecast_ml", [333, 351, 376], ["350", "350", "400"]),
    ("moisture_balance_today_ml", [123, 127, -4], ["120", "130", "0"]),
])
async def test_clock_driven_sensors_publish_in_steps(hass, key, values, expected) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    entity_id = _id(hass, entry, key)
    states = []
    for value in values:
        coordinator.async_set_updated_data({**coordinator.data, key: value})
        await hass.async_block_till_done()
        states.append(hass.states.get(entity_id).state)
    assert states == expected
    await _unload(hass, entry)


async def test_the_forecast_temperature_change_has_a_deadband(hass) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    house_id, room_id = _id(hass, entry, "forecast_temperature_change_c"), _id(hass, entry, "wohnzimmer_forecast_temperature_change_c")
    seen = []
    for value in (-0.3, -0.4, -0.3, -0.5, -0.4, 0.0, -0.1):
        coordinator.data["rooms"]["wohnzimmer"]["forecast_temperature_change_c"] = value
        coordinator.async_set_updated_data({**coordinator.data, "forecast_temperature_change_c": value})
        await hass.async_block_till_done()
        seen.append((float(hass.states.get(house_id).state), float(hass.states.get(room_id).state)))
    assert [house for house, _ in seen] == [-0.3, -0.3, -0.3, -0.5, -0.5, 0.0, -0.1]
    assert [room for _, room in seen] == [house for house, _ in seen]
    await _unload(hass, entry)
