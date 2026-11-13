"""0.26.7.0 support case A (real Home Assistant runtime): contacts in the floor plan.

Summarised evidence only (no raw diagnosis): six rooms, the hall without own contacts, several contacts are
``input_select`` helpers instead of binary sensors, and ``cross_ventilation_pairs`` holds three-room chains
("Wohnzimmer+Flur+Schlafzimmer, …"). This test rebuilds that shape with invented entity ids:

1. a room with a binary and a multi-state (input_select) contact,
2. a window drawn physically in the hall (room A) whose input_select contact belongs to the living room (room B),
3. the contact is chosen in the plan, saved, the integration is reloaded and the helper changes its state,
4. physical place (hall), logical room (living room) and live state (tilted/open/closed) all stay right,
5. the stored chains are kept unchanged and shown as a repair notice with the reason – not ignored silently.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.freshairiq import house_map
from custom_components.freshairiq.const import CONF_ROOM_CONTACTS, DOMAIN
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload
from ha_tests.test_house_map_026504 import _call

BINARY = "binary_sensor.wz_fenster_links"
SELECT = "input_select.wz_fenster_flur"          # multi-state helper, physically in the hall
OPTIONS3 = ["geschlossen", "gekippt", "offen"]
CHAINS = "Wohnzimmer+Flur+Schlafzimmer,Wohnzimmer+Flur+Arbeitszimmer,Arbeitszimmer+Flur+Schlafzimmer"
LAYOUT = {
    "schema_version": 1, "revision": 0, "building": {"north_deg": 0, "units": "m", "north_confirmed": True},
    "floors": [{"id": "f_eg", "name": "EG", "level_key": "EG", "order": 0}],
    "rooms": [
        {"id": "r_wz", "room_key": "wohnzimmer", "floor_id": "f_eg", "polygon": [[0, 0], [5, 0], [5, 4], [0, 4]], "provenance": "user"},
        {"id": "r_flur", "room_key": "flur", "floor_id": "f_eg", "polygon": [[5, 0], [7, 0], [7, 4], [5, 4]], "provenance": "user"},
    ],
    "openings": [
        {"id": "w_wz", "room_id": "r_wz", "edge": 0, "offset": 0.5, "width_m": 1.0, "kind": "window", "mechanics": "unknown", "contacts": [BINARY]},
        # drawn in the hall, sensor of the living room's setup
        {"id": "w_flur", "room_id": "r_flur", "edge": 1, "offset": 0.5, "width_m": 0.8, "kind": "window", "mechanics": "tilt", "contacts": [SELECT]},
    ],
    "connections": [], "shading": [],
}


def _rooms():
    wz = {**_room("wohnzimmer", "Wohnzimmer"), CONF_ROOM_CONTACTS: [BINARY, SELECT], "length": 5, "width": 4}
    flur = {**_room("flur", "Flur"), CONF_ROOM_CONTACTS: [], "length": 2, "width": 4}
    schlaf = {**_room("schlafzimmer", "Schlafzimmer"), CONF_ROOM_CONTACTS: ["binary_sensor.sz_fenster"], "length": 4, "width": 4}
    arbeit = {**_room("arbeitszimmer", "Arbeitszimmer"), CONF_ROOM_CONTACTS: ["binary_sensor.az_fenster"], "length": 3, "width": 3}
    return [wz, flur, schlaf, arbeit]


async def _settle(hass, coordinator, freezer, seconds: float = 5.0) -> None:
    """Let the three-state debounce see a stable state (3 s), then refresh."""
    await coordinator.async_refresh()
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_window_in_the_hall_reports_the_living_rooms_input_select_after_save_and_reload(hass, hass_ws_client, freezer) -> None:
    _set_sources(hass, "wohnzimmer", "flur", "schlafzimmer", "arbeitszimmer")
    hass.states.async_set(BINARY, "off", {"device_class": "window"})
    hass.states.async_set(SELECT, "geschlossen", {"options": OPTIONS3})
    for contact in ("binary_sensor.sz_fenster", "binary_sensor.az_fenster"):
        hass.states.async_set(contact, "off", {"device_class": "window"})
    entry = await _setup(hass, _entry(rooms=_rooms(), options={"cross_ventilation_pairs": CHAINS}))
    client = await hass_ws_client(hass)

    # 3: choose, save, read back
    assert (await _call(client, 1, type=house_map.SAVE, layout=LAYOUT, base_revision=0))["success"]
    stored = (await _call(client, 2, type=house_map.GET))["result"]
    assert stored["issues"] == []
    assert {o["id"]: (o["room_id"], o["contacts"]) for o in stored["layout"]["openings"]} == {
        "w_wz": ("r_wz", [BINARY]), "w_flur": ("r_flur", [SELECT])}

    # reload the integration – the plan and the room setup come back unchanged
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    coordinator = entry.runtime_data
    client = await hass_ws_client(hass)
    again = (await _call(client, 3, type=house_map.GET))["result"]["layout"]
    assert {o["id"]: (o["room_id"], o["contacts"]) for o in again["openings"]} == {"w_wz": ("r_wz", [BINARY]), "w_flur": ("r_flur", [SELECT])}
    assert coordinator.data["rooms"]["wohnzimmer"]["contact_entities"] == [BINARY, SELECT]   # logical room unchanged
    assert coordinator.data["rooms"]["flur"].get("contact_entities") in ([], None)

    # 4: the helper changes – physical place stays the hall, logical room stays the living room, live state follows
    for raw, expected in (("gekippt", "tilted"), ("offen", "open"), ("geschlossen", "closed")):
        hass.states.async_set(SELECT, raw, {"options": OPTIONS3})
        await _settle(hass, coordinator, freezer)
        payload = house_map.live_payload(hass, entry, again)
        live = payload["rooms"]["wohnzimmer"]["contacts"][SELECT]
        assert live["three_state"] is True and live["state"] == expected, raw
        assert SELECT not in payload["rooms"]["flur"]["contacts"]
        opening = payload["airflow"]["openings"]["w_flur"]
        assert (opening["room"], opening["state"]) == ("r_flur", expected), raw
        # the binary sensor next to it keeps its own state
        assert payload["rooms"]["wohnzimmer"]["contacts"][BINARY]["state"] == "closed"

    # 5: the three-room chains are kept as written and named in a repair notice (not dropped, not silent)
    assert entry.options["cross_ventilation_pairs"] == CHAINS
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"cross_pairs_unused_{entry.entry_id}")
    assert issue is not None and issue.translation_key == "cross_pairs_unused"
    detail = issue.translation_placeholders["detail"]
    assert "Wohnzimmer+Flur+Schlafzimmer" in detail and "Wohnzimmer+Schlafzimmer" in detail and "(Flur)" in detail
    await _unload(hass, entry)
    await asyncio.sleep(0)


async def test_repair_notice_disappears_once_the_pairs_are_valid(hass) -> None:
    _set_sources(hass, "wohnzimmer", "flur", "schlafzimmer", "arbeitszimmer")
    entry = await _setup(hass, _entry(rooms=_rooms(), options={"cross_ventilation_pairs": "Wohnzimmer+Schlafzimmer"}))
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"cross_pairs_unused_{entry.entry_id}") is None
    assert entry.options["cross_ventilation_pairs"] == "wohnzimmer+schlafzimmer"
    await _unload(hass, entry)
