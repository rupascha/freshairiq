"""Optional house map (0.26.5.4): layout store and websocket API in a real Home Assistant.

* ``get`` serves the stored layout (or nothing yet) with its issues and the rooms to draw;
* ``propose`` builds a deterministic proposal without saving it;
* ``save`` is for administrators only, validates, limits the size and refuses a revision conflict;
* ``subscribe`` pushes wind, per-contact states (binary open = "open – kind unknown",
  pending while no session runs) and the air-path hypothesis, only when something changed;
* the coordinator data, the dashboard live payload and the entities stay untouched.
"""
from __future__ import annotations

import asyncio

from custom_components.freshairiq import house_map
from custom_components.freshairiq.const import CONF_CONTACT_DELAYS, CONF_OUTDOOR_WEATHER
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload


async def _no_message(client) -> bool:
    try:
        await asyncio.wait_for(client.receive_json(), 0.2)
    except TimeoutError:
        return True
    return False


async def _call(client, msg_id: int, events: list | None = None, **payload):
    await client.send_json({"id": msg_id, **payload})
    reply = await client.receive_json()
    while reply.get("id") != msg_id or reply.get("type") == "event":
        if events is not None and reply.get("type") == "event":
            events.append(reply["event"])
        reply = await client.receive_json()
    return reply


def _house_entry():
    bad = {**_room("bad", "Bad"), CONF_CONTACT_DELAYS: {"binary_sensor.bad_window": 120}}
    flur = {**_room("flur", "Flur"), "contacts": ["binary_sensor.flur_window", "binary_sensor.bad_window"], "length": 6, "width": 2}
    return _entry(rooms=[bad, flur], options={"open_connections": {"flur": ["bad"]}})


async def test_house_map_get_propose_save_and_conflicts(hass, hass_ws_client) -> None:
    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    data_before = dict(entry.runtime_data.data)
    client = await hass_ws_client(hass)

    reply = await _call(client, 1, type=house_map.GET)
    result = reply["result"]
    assert result["house_map_api"] == "house_map_v1" and result["stored"] is False and result["revision"] == 0
    assert result["reconcile"]["missing"] == ["bad", "flur"] and {r["key"] for r in result["rooms"]} == {"bad", "flur"}

    proposal = (await _call(client, 2, type=house_map.PROPOSE, entry_id=entry.entry_id))["result"]
    assert proposal["issues"] == [] and {r["room_key"] for r in proposal["layout"]["rooms"]} == {"bad", "flur"}
    assert proposal["quality"]["provenance"] == {"bad": "estimated", "flur": "config"}
    layout = proposal["layout"]

    saved = await _call(client, 3, type=house_map.SAVE, layout=layout, base_revision=0)
    assert saved["success"] and saved["result"]["revision"] == 1
    conflict = await _call(client, 4, type=house_map.SAVE, layout=layout, base_revision=0)
    assert conflict["error"]["code"] == "revision_conflict"
    broken = {**layout, "rooms": [{**layout["rooms"][0], "polygon": [[0, 0], [1, 0]]}] + layout["rooms"][1:]}
    invalid = await _call(client, 5, type=house_map.SAVE, layout=broken, base_revision=1)
    assert invalid["error"]["code"] == "invalid_layout" and "E_POLY_POINTS" in invalid["error"]["message"]
    huge = await _call(client, 6, type=house_map.SAVE, layout={**layout, "pad": "x" * (house_map.MAX_LAYOUT_BYTES + 1)}, base_revision=1)
    assert huge["error"]["code"] == "too_large"

    result = (await _call(client, 7, type=house_map.GET, entry_id=entry.entry_id))["result"]
    assert result["revision"] == 1 and result["stored"] is True and result["issues"] == [] and result["reconcile"]["missing"] == []
    missing_only = (await _call(client, 8, type=house_map.PROPOSE, missing_only=True))["result"]
    assert [r["polygon"] for r in missing_only["layout"]["rooms"]] == [r["polygon"] for r in result["layout"]["rooms"]]

    # the house map never changes FreshAirIQ's own data
    assert entry.runtime_data.data.keys() == data_before.keys()
    await _unload(hass, entry)
    for msg_id, kind in ((9, house_map.GET), (10, house_map.PROPOSE)):
        assert (await _call(client, msg_id, type=kind))["error"]["code"] == "not_loaded"
    assert (await _call(client, 11, type=house_map.SAVE, layout={}, base_revision=0))["error"]["code"] == "not_loaded"
    assert (await _call(client, 12, type=house_map.SUBSCRIBE))["error"]["code"] == "not_loaded"


async def test_saving_requires_an_administrator(hass, hass_ws_client, hass_read_only_access_token) -> None:
    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    client = await hass_ws_client(hass, hass_read_only_access_token)
    assert (await _call(client, 1, type=house_map.GET))["success"] is True
    reply = await _call(client, 2, type=house_map.SAVE, layout={}, base_revision=0)
    assert reply["success"] is False and reply["error"]["code"] == "unauthorized"
    await _unload(hass, entry)


async def test_unknown_stored_schema_is_shown_not_guessed(hass, hass_ws_client) -> None:
    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    store = await house_map._store(hass, entry.entry_id)
    store.raw = {"schema_version": 9, "revision": 4}
    client = await hass_ws_client(hass)
    result = (await _call(client, 1, type=house_map.GET))["result"]
    assert result["layout"] is None and result["error_code"] == "E_SCHEMA_VERSION" and result["revision"] == 4
    assert result["reconcile"]["missing"] == ["bad", "flur"]
    proposal = (await _call(client, 2, type=house_map.PROPOSE, missing_only=True))["result"]
    assert {r["room_key"] for r in proposal["layout"]["rooms"]} == {"bad", "flur"}
    await _unload(hass, entry)


async def test_live_channel_contacts_wind_and_paths(hass, hass_ws_client) -> None:
    _set_sources(hass, "bad", "flur")
    hass.states.async_set("weather.home", "cloudy", {"wind_bearing": "NW", "wind_speed": 18, "wind_speed_unit": "km/h"})
    entry = await _setup(hass, _house_entry())
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_OUTDOOR_WEATHER: "weather.home"})
    client = await hass_ws_client(hass)
    proposal = (await _call(client, 1, type=house_map.PROPOSE))["result"]["layout"]
    proposal["building"]["north_confirmed"] = True
    assert (await _call(client, 2, type=house_map.SAVE, layout=proposal, base_revision=0))["success"]

    await client.send_json({"id": 3, "type": house_map.SUBSCRIBE, "entry_id": entry.entry_id})
    assert (await client.receive_json())["success"] is True
    event = (await client.receive_json())["event"]
    assert event["house_map_api"] == "house_map_v1" and event["revision"] == 1 and event["layout_usable"] is True
    assert event["wind"]["from_deg"] == 315.0 and event["wind"]["speed_ms"] == 5.0 and event["wind"]["source"] == "weather.home"
    assert event["rooms"]["bad"]["contacts"]["binary_sensor.bad_window"] == {"state": "closed", "pending": False, "three_state": False, "delay_s": 120.0, "open_s": None}
    assert event["airflow"]["model_level"] == "topology_only" and event["airflow"]["paths"] == []

    entry.runtime_data.async_update_listeners()  # nothing changed: nothing sent
    assert await _no_message(client)

    hass.states.async_set("binary_sensor.bad_window", "on")
    await hass.async_block_till_done()
    entry.runtime_data.async_update_listeners()
    event = (await asyncio.wait_for(client.receive_json(), 2))["event"]
    contact = event["rooms"]["bad"]["contacts"]["binary_sensor.bad_window"]
    assert contact["state"] == "open_unspecified" and contact["pending"] is True  # 120 s delay: no session yet
    # audit (10): the shared contact has no delay in the hall (independent room gates) -> not "confirmation running" there
    assert event["rooms"]["flur"]["contacts"]["binary_sensor.bad_window"]["pending"] is False
    assert event["airflow"]["pending_openings"]

    # a save from another editor reaches the open map
    proposal["building"]["north_deg"] = 30.0
    seen: list = []
    assert (await _call(client, 4, events=seen, type=house_map.SAVE, layout=proposal, base_revision=1))["success"]
    while not any(e.get("revision") == 2 for e in seen):
        seen.append((await asyncio.wait_for(client.receive_json(), 2))["event"])

    await _unload(hass, entry)
    await asyncio.sleep(0.1)
    while not await _no_message(client):  # drain what was still on its way
        pass
    house_map.async_dispatcher_send(hass, house_map._signal(entry.entry_id))  # nothing is served for an unloaded entry
    await hass.async_block_till_done()
    assert await _no_message(client)
    reply = await _call(client, 5, type="unsubscribe_events", subscription=3)
    assert reply["success"] is True


async def test_live_payload_without_weather_layout_or_room_data(hass) -> None:
    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    entry.runtime_data.data = {**entry.runtime_data.data, "rooms": {**entry.runtime_data.data["rooms"], "junk": "x"}}
    hass.states.async_remove("binary_sensor.flur_window")
    payload = house_map.live_payload(hass, entry, None)
    assert payload["airflow"] is None and payload["layout_usable"] is False
    assert payload["wind"]["reason"] == "no_direction" and payload["wind"]["source"] is None
    assert payload["rooms"]["flur"]["contacts"]["binary_sensor.flur_window"]["state"] == "unknown"
    assert "junk" not in payload["rooms"]
    await _unload(hass, entry)


async def test_audit10_real_room_payload_delay_and_fan_lists(hass, freezer) -> None:
    """Audit (10): the map reads only fields a real room publishes; 'pending' means a running delay; fans by entity."""
    import json
    from datetime import timedelta
    from pathlib import Path

    from homeassistant.util import dt as dt_util

    _set_sources(hass, "bad", "flur")
    hass.states.async_set("fan.a", "on"); hass.states.async_set("fan.b", "off")
    bad = {**_room("bad", "Bad"), CONF_CONTACT_DELAYS: {"binary_sensor.bad_window": 0}, "exhaust_fan": ["fan.a", "fan.b"]}
    flur = {**_room("flur", "Flur"), CONF_CONTACT_DELAYS: {"binary_sensor.flur_window": 120}, "exhaust_fan": ["fan.b", "fan.a"]}
    freezer.move_to(dt_util.utcnow())
    entry = await _setup(hass, _entry(rooms=[bad, flur]))
    room = entry.runtime_data.data["rooms"]["bad"]
    # P0 contract: the mould limits are options, the room publishes its level
    assert "mould_level" in room and "mould_warn_surface_rh" not in room and "mould_critical_surface_rh" not in room
    fixture = json.loads((Path(__file__).resolve().parents[1] / "frontend_tests/fixtures/house_room_payload.json").read_text(encoding="utf-8"))["room"]
    assert set(fixture) <= set(room) | {"house_aligned_action"}, set(fixture) - set(room)

    hass.states.async_set("binary_sensor.bad_window", "on"); hass.states.async_set("binary_sensor.flur_window", "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    await entry.runtime_data.async_refresh()
    for key in ("bad", "flur"):  # make sure the evaluation of "no session" does not depend on the delay alone
        entry.runtime_data.data["rooms"][key]["active"] = False
    payload = house_map.live_payload(hass, entry, None)
    bad_contact = payload["rooms"]["bad"]["contacts"]["binary_sensor.bad_window"]
    flur_contact = payload["rooms"]["flur"]["contacts"]["binary_sensor.flur_window"]
    assert bad_contact["state"] == "open_unspecified" and bad_contact["pending"] is False and bad_contact["open_s"] >= 30  # 0 s delay
    assert flur_contact["pending"] is True  # 120 s delay still running
    freezer.tick(timedelta(seconds=100))
    payload = house_map.live_payload(hass, entry, None)
    assert payload["rooms"]["flur"]["contacts"]["binary_sensor.flur_window"]["pending"] is False  # delay over
    assert payload["rooms"]["bad"]["exhaust_fan"] == ["fan.a", "fan.b"] and payload["rooms"]["flur"]["exhaust_fans"] == {"fan.b": False, "fan.a": True}
    assert payload["rooms"]["bad"]["mechanical_exhaust_active"] is True  # fan.a runs: read from configured_actuators
    # the shared fans become one device per entity, whatever the configured order
    layout = house_map.normalise({"schema_version": 1, "floors": [{"id": "f"}], "rooms": [
        {"id": "rb", "room_key": "bad", "floor_id": "f", "polygon": [[0, 0], [4, 0], [4, 4], [0, 4]]},
        {"id": "rf", "room_key": "flur", "floor_id": "f", "polygon": [[4, 0], [8, 0], [8, 4], [4, 4]]}]})
    devices = house_map.live_payload(hass, entry, layout)["airflow"]["devices"]
    assert devices == [{"fan": "fan.a", "rooms": ["rb", "rf"], "active": True}, {"fan": "fan.b", "rooms": ["rb", "rf"], "active": False}]
    await _unload(hass, entry)


async def test_floor_plan_template_is_stored_per_floor_for_administrators(hass, hass_ws_client, hass_read_only_access_token) -> None:
    """The picture lives in its own store per floor; ``get`` only says which floors have one."""
    import base64

    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    client = await hass_ws_client(hass)
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\0" * 64).decode()
    underlay = {"floor_id": "f_eg", "mime": "image/jpeg", "data": jpeg, "width": 800, "height": 600, "scale_m_per_px": 0.02,
                "walls": [[402, 140, 402, 175]], "close_px": 3}

    assert (await _call(client, 1, type=house_map.GET))["result"]["underlays"] == {}
    assert (await _call(client, 2, type=house_map.UNDERLAY_GET, floor_id="f_eg"))["result"]["underlay"] is None
    saved = await _call(client, 3, type=house_map.UNDERLAY_SAVE, underlay=underlay)
    assert saved["result"]["underlays"] == {"f_eg": {"width": 800, "height": 600, "calibrated": True}}
    stored = (await _call(client, 4, type=house_map.UNDERLAY_GET, entry_id=entry.entry_id, floor_id="f_eg"))["result"]["underlay"]
    assert stored["data"] == jpeg and stored["walls"] == [[402.0, 140.0, 402.0, 175.0]] and stored["close_px"] == 3
    got = (await _call(client, 5, type=house_map.GET))["result"]
    assert got["underlays"] == {"f_eg": {"width": 800, "height": 600, "calibrated": True}} and "data" not in str(got["underlays"])
    # sizes for the suggestions come from the room setup
    assert {r["key"]: r["length"] for r in got["rooms"]} == {"bad": None, "flur": 6}

    refused = await _call(client, 6, type=house_map.UNDERLAY_SAVE, underlay={**underlay, "mime": "image/png"})
    assert refused["error"] == {"code": "invalid_underlay", "message": "E_UNDERLAY_DATA"}
    no_floor = await _call(client, 7, type=house_map.UNDERLAY_SAVE, underlay={**underlay, "floor_id": ""})
    assert no_floor["error"]["code"] == "invalid_underlay" and no_floor["error"]["message"] == "E_UNDERLAY_FLOOR"

    # readers may look, not change
    reader = await hass_ws_client(hass, hass_read_only_access_token)
    assert (await _call(reader, 1, type=house_map.UNDERLAY_GET, floor_id="f_eg"))["success"] is True
    for msg_id, payload in ((2, {"type": house_map.UNDERLAY_SAVE, "underlay": underlay}), (3, {"type": house_map.UNDERLAY_DELETE, "floor_id": "f_eg"})):
        assert (await _call(reader, msg_id, **payload))["error"]["code"] == "unauthorized"

    # the template survives a restart of the store and is removed on request
    hass.data.pop("freshairiq_house_underlay_stores")
    assert (await _call(client, 8, type=house_map.UNDERLAY_GET, floor_id="f_eg"))["result"]["underlay"]["data"] == jpeg
    deleted = await _call(client, 9, type=house_map.UNDERLAY_DELETE, floor_id="f_eg")
    assert deleted["result"]["underlays"] == {}
    assert (await _call(client, 10, type=house_map.UNDERLAY_GET, floor_id="f_eg"))["result"]["underlay"] is None

    await _unload(hass, entry)
    for msg_id, payload in ((11, {"type": house_map.UNDERLAY_GET, "floor_id": "f_eg"}), (12, {"type": house_map.UNDERLAY_SAVE, "underlay": underlay}),
                            (13, {"type": house_map.UNDERLAY_DELETE, "floor_id": "f_eg"})):
        assert (await _call(client, msg_id, **payload))["error"]["code"] == "not_loaded"


async def test_removing_the_integration_deletes_plan_and_template(hass, hass_ws_client, hass_storage) -> None:
    """Deleting the entry removes its floor plan and template files; another entry keeps its own."""
    import base64

    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    client = await hass_ws_client(hass)
    layout = (await _call(client, 1, type=house_map.PROPOSE))["result"]["layout"]
    assert (await _call(client, 2, type=house_map.SAVE, layout=layout, base_revision=0))["success"]
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\0" * 64).decode()
    underlay = {"floor_id": "f_eg", "mime": "image/jpeg", "data": jpeg, "width": 800, "height": 600}
    assert (await _call(client, 3, type=house_map.UNDERLAY_SAVE, underlay=underlay))["success"]
    keys = {f"freshairiq.house_layout.{entry.entry_id}", f"freshairiq.house_underlay.{entry.entry_id}"}
    other = {"freshairiq.house_layout.other_entry": {"version": 1, "data": {}}, "freshairiq.house_underlay.other_entry": {"version": 1, "data": {}}}
    hass_storage.update(other)
    assert keys <= set(hass_storage)

    assert (await hass.config_entries.async_remove(entry.entry_id))["require_restart"] is False
    await hass.async_block_till_done()
    assert not keys & set(hass_storage)
    assert set(other) <= set(hass_storage)
    # no stale copy in memory either
    for cache in ("freshairiq_house_layout_stores", "freshairiq_house_underlay_stores"):
        assert entry.entry_id not in hass.data.get(cache, {})


# Hotfix F01 (31.10.): the house map card holds exactly these two subscriptions; after both are released
# (card removed) no channel sends anything any more, also when the room data and the layout change.
async def test_the_card_pair_of_subscriptions_ends_completely(hass, hass_ws_client) -> None:
    _set_sources(hass, "bad", "flur")
    entry = await _setup(hass, _house_entry())
    client = await hass_ws_client(hass)
    proposal = (await _call(client, 1, type=house_map.PROPOSE))["result"]["layout"]
    assert (await _call(client, 2, type=house_map.SAVE, layout=proposal, base_revision=0))["success"]
    seen: list = []
    assert (await _call(client, 3, events=seen, type="freshairiq/dashboard/subscribe", entry_id=entry.entry_id))["success"]
    assert (await _call(client, 4, events=seen, type=house_map.SUBSCRIBE, entry_id=entry.entry_id))["success"]
    while await _no_message(client) is False:  # the first payload of each channel
        pass
    coordinator = entry.runtime_data
    coordinator.async_set_updated_data({**coordinator.data, "status_text": "vorher"})
    await hass.async_block_till_done()
    assert not await _no_message(client)  # live while subscribed
    while not await _no_message(client):
        pass
    for msg_id, subscription in ((5, 3), (6, 4)):
        assert (await _call(client, msg_id, type="unsubscribe_events", subscription=subscription))["success"]
    coordinator.async_set_updated_data({**coordinator.data, "status_text": "danach"})
    house_map.async_dispatcher_send(hass, house_map._signal(entry.entry_id))
    await hass.async_block_till_done()
    assert await _no_message(client)  # nothing from either channel
    proposal["building"]["north_deg"] = 45.0
    assert (await _call(client, 7, type=house_map.SAVE, layout=proposal, base_revision=1))["success"]
    assert await _no_message(client)
    await _unload(hass, entry)
