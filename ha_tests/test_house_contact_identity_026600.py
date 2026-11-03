"""Hotfix after review (F01/F02), real Home Assistant runtime: where a window is drawn, which sensor it has and which
room it airs are independent.

A guest WC window is set up as a way to air the hall (its contact belongs to the hall's setup), but it is drawn in the
WC. The contact goes Home Assistant -> coordinator (hall) -> live payload -> air paths -> map: the WC window shows the
sensor's real state, the WC door its own sensor's, the hall's decision is the same with or without the plan, and a
saved plan keeps the assignment.
"""
from __future__ import annotations

import asyncio

from custom_components.freshairiq import house_map
from custom_components.freshairiq.const import CONF_CONTACT_KINDS, CONF_ROOM_CONTACTS
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload
from ha_tests.test_house_map_026504 import _call

WC_WINDOW, WC_DOOR = "binary_sensor.wc_fenster", "binary_sensor.wc_tuer"
LAYOUT = {
    "schema_version": 1, "revision": 0, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
    "floors": [{"id": "f_eg", "name": "EG", "level_key": "EG", "order": 0}],
    "rooms": [
        {"id": "r_flur", "room_key": "flur", "floor_id": "f_eg", "polygon": [[0, 0], [5, 0], [5, 2], [0, 2]], "provenance": "user"},
        # drawn clockwise on purpose: the window's outside must still be found (F03 shares the normals)
        {"id": "r_wc", "room_key": "wc", "floor_id": "f_eg", "polygon": [[0, 2], [0, 3.5], [1.5, 3.5], [1.5, 2]], "provenance": "user"},
    ],
    "openings": [
        {"id": "w_wc", "room_id": "r_wc", "edge": 1, "offset": 0.5, "width_m": 0.6, "kind": "window", "mechanics": "tilt", "contacts": [WC_WINDOW]},
        {"id": "d_wc", "room_id": "r_wc", "edge": 3, "offset": 0.5, "width_m": 0.8, "kind": "door", "mechanics": "door", "contacts": [WC_DOOR], "interior": True},
    ],
    "connections": [], "shading": [],
}


def _wc_entry():
    flur = {**_room("flur", "Flur"), CONF_ROOM_CONTACTS: ["binary_sensor.flur_window", WC_WINDOW, WC_DOOR],
            CONF_CONTACT_KINDS: {WC_WINDOW: "window", WC_DOOR: "door"}, "length": 5, "width": 2}
    wc = {**_room("wc", "Gäste-WC"), CONF_ROOM_CONTACTS: [], "length": 1.5, "width": 1.5}
    return _entry(rooms=[flur, wc])


async def test_wc_window_drawn_in_the_wc_shows_the_halls_sensor_and_decisions_stay(hass, hass_ws_client) -> None:
    _set_sources(hass, "flur", "wc")
    hass.states.async_set(WC_WINDOW, "off", {"device_class": "window"})
    hass.states.async_set(WC_DOOR, "off", {"device_class": "door"})
    entry = await _setup(hass, _wc_entry())
    client = await hass_ws_client(hass)
    coordinator = entry.runtime_data
    before = {k: coordinator.data["rooms"]["flur"].get(k) for k in ("action", "house_aligned_action", "reason", "contact_entities")}
    assert WC_WINDOW in before["contact_entities"] and coordinator.data["rooms"]["wc"].get("contact_entities") in ([], None)

    # 5: the manual assignment is saved and comes back unchanged
    assert (await _call(client, 1, type=house_map.SAVE, layout=LAYOUT, base_revision=0))["success"]
    stored = (await _call(client, 2, type=house_map.GET))["result"]
    assert stored["issues"] == []
    assert {o["id"]: (o["room_id"], o["contacts"]) for o in stored["layout"]["openings"]} == {"w_wc": ("r_wc", [WC_WINDOW]), "d_wc": ("r_wc", [WC_DOOR])}

    # 1 + 2: the WC window opens – the WC window (drawn in the WC) is open, the WC door (own sensor) stays closed
    hass.states.async_set(WC_WINDOW, "on", {"device_class": "window"})
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    payload = house_map.live_payload(hass, entry, stored["layout"])
    assert payload["rooms"]["flur"]["contacts"][WC_WINDOW]["state"] == "open_unspecified"
    assert WC_WINDOW not in payload["rooms"]["wc"]["contacts"]            # the setup is unchanged: the hall airs by it
    window, door = payload["airflow"]["openings"]["w_wc"], payload["airflow"]["openings"]["d_wc"]
    assert (window["room"], window["target"], window["state"]) == ("r_wc", "outside", "open_unspecified")
    assert window["facade_deg"] == 0.0     # clockwise WC: its north wall faces north (the old normal gave 180°)
    assert (door["target"], door["state"]) == ("r_flur", "closed")
    hass.states.async_set(WC_DOOR, "on", {"device_class": "door"})
    await hass.async_block_till_done()
    assert house_map.live_payload(hass, entry, stored["layout"])["airflow"]["openings"]["d_wc"]["state"] == "open_unspecified"

    # 10: the hall's decision does not depend on the plan – the same with the plan saved, the window open as before
    hass.states.async_set(WC_DOOR, "off", {"device_class": "door"})
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    with_plan = {k: coordinator.data["rooms"]["flur"].get(k) for k in before}
    assert with_plan["contact_entities"] == before["contact_entities"]
    assert entry.runtime_data.data.keys() == coordinator.data.keys()

    # the proposal (F02): the WC window used only by the hall is drawn in the hall – nothing turns it into a door
    proposal = (await _call(client, 3, type=house_map.PROPOSE))["result"]["layout"]
    assert not [o for o in proposal["openings"] if o["kind"] == "door" and WC_WINDOW in o["contacts"]]
    await _unload(hass, entry)
    await asyncio.sleep(0)


async def test_proposal_reads_the_sensor_kind_from_home_assistant(hass, hass_ws_client) -> None:
    """3 + 4: one contact in two rooms' setup – a window sensor is drawn once, a door sensor between the rooms."""
    _set_sources(hass, "flur", "wc")
    hass.states.async_set(WC_WINDOW, "off", {"device_class": "window"})
    hass.states.async_set(WC_DOOR, "off", {"device_class": "door"})
    flur = {**_room("flur", "Flur"), CONF_ROOM_CONTACTS: ["binary_sensor.flur_window", WC_WINDOW, WC_DOOR], "length": 5, "width": 2}
    wc = {**_room("wc", "Gäste-WC"), CONF_ROOM_CONTACTS: [WC_WINDOW, WC_DOOR], "length": 1.5, "width": 1.5}
    entry = await _setup(hass, _entry(rooms=[flur, wc]))
    client = await hass_ws_client(hass)
    layout = (await _call(client, 1, type=house_map.PROPOSE))["result"]["layout"]
    windows = [o for o in layout["openings"] if WC_WINDOW in o["contacts"]]
    doors = [o for o in layout["openings"] if WC_DOOR in o["contacts"]]
    assert [(o["room_id"], o["kind"]) for o in windows] == [("r_wc", "window")]   # once, in the smaller room
    assert [(o["kind"], o["contacts"]) for o in doors] == [("door", [WC_DOOR])]     # the real shared door is drawn
    assert not [c for c in layout["connections"] if WC_WINDOW in c.get("contacts", [])]
    await _unload(hass, entry)
