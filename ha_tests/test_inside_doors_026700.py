"""0.26.7.0: inside doors are no outside openings (real coordinator, Home Assistant states).

Before: an inside door counted like a window – opened alone it started an airing, and in the
contact mode "all" a closed inside door blocked the airing of an open window. A contact is an
inside opening only when the user says so (``contact_sides``); older configurations keep the
outside behaviour.
"""
from __future__ import annotations

from datetime import datetime

from custom_components.freshairiq.robustness import prepare_runtime_rooms
from ha_tests.test_cov_coordinator_b import (  # noqa: F401 - fixture re-export
    BERLIN, DOOR, HUM, OPTIONS, TEMP, WINDOW, _cleanup_coordinators, _data, _make, _room,
)

START = datetime(2026, 10, 27, 20, 0, tzinfo=BERLIN)
WIN, IDOOR = "binary_sensor.bad_fenster", "binary_sensor.bad_innentuer"
FLUR_WIN = "binary_sensor.flur_fenster"
LAGE = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
BASE = {
    "sensor.bad_t": (21.0, TEMP), "sensor.bad_h": (72.0, HUM), "sensor.flur_t": (20.5, TEMP), "sensor.flur_h": (66.0, HUM),
    "sensor.aussen_t": (9.0, TEMP), "sensor.aussen_h": (70.0, HUM),
    WIN: ("off", WINDOW), IDOOR: ("off", DOOR), FLUR_WIN: ("off", WINDOW),
}


def _rooms(*, side: str | None = "inside", mode: str = "any", connected: str | None = None, flur_floor="ground_floor",
           flur_contacts=(FLUR_WIN,), flur_sides=None, door=IDOOR):
    bad = _room("bad", "Bad", "ground_floor", temp=["sensor.bad_t"], hum=["sensor.bad_h"], contacts=[WIN, door], volume=20, mode=mode)
    flur = _room("flur", "Flur", flur_floor, temp=["sensor.flur_t"], hum=["sensor.flur_h"], contacts=list(flur_contacts), volume=30, sort=1)
    if side:
        bad["contact_sides"] = {door: side}
    if connected:
        bad["contact_connected_rooms"] = {door: connected}
    if flur_sides:
        flur["contact_sides"] = flur_sides
    return [bad, flur]


async def _settled(hass, freezer, rooms, options=OPTIONS, initial=None):
    d = await _make(hass, freezer, start=START, data=_data(rooms), options=options, initial={**BASE, **(initial or {})})
    for _ in range(3):
        await d.step(60)
    return d


def _quiet(d, room="bad"):
    mem, result = d.mem(room), d.room(room)
    return {"session": bool(mem.get("session_active")), "open": bool(result.get("open")), "active": bool(result.get("active")),
            "samples": int(mem.get("learning_samples", 0) or 0), "sessions_today": len(mem.get("completed_sessions") or [])}


async def test_inside_door_alone_starts_no_airing_reference_learning_or_statistics(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms())
    before = (_quiet(d), d.room("bad")["action"], d.room("bad").get("reference_humidity"))
    for _ in range(12):
        await d.step(60, **{IDOOR.replace(".", "__"): "on"})
    after = _quiet(d)
    assert after == before[0] and after["session"] is False and after["open"] is False
    assert d.room("bad")["action"] == before[1] and d.room("bad").get("reference_humidity") == before[2]
    assert d.room("bad")["contact_entities"] == [WIN] and d.room("bad")["inside_contact_entities"] == [IDOOR]
    assert d.room("bad")["contact_count"] == 1
    await d.finish(**{IDOOR.replace(".", "__"): "off"})
    assert _quiet(d)["samples"] == before[0]["samples"] and not d.mem("bad").get("session_active")


async def test_window_alone_and_window_with_open_inside_door_behave_the_same(hass, freezer) -> None:
    runs = []
    for door_state in ("off", "on"):
        d = await _settled(hass, freezer, _rooms())
        await d.step(60, **{IDOOR.replace(".", "__"): door_state})
        for _ in range(4):
            await d.step(60, **{WIN.replace(".", "__"): "on"})
        room = d.room("bad")
        runs.append((bool(d.mem("bad").get("session_active")), room["active"], room["action"], room.get("reference_humidity")))
        await d.finish(**{WIN.replace(".", "__"): "off", IDOOR.replace(".", "__"): "off"})
    assert runs[0] == runs[1] and runs[0][0] is True


async def test_mode_all_a_closed_inside_door_no_longer_blocks_the_open_window(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms(mode="all"))
    for _ in range(4):
        await d.step(60, **{WIN.replace(".", "__"): "on"})
    assert d.mem("bad").get("session_active") is True and d.room("bad")["open"] is True
    await d.finish(**{WIN.replace(".", "__"): "off"})


async def test_older_configuration_without_a_side_keeps_the_outside_behaviour(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms(side=None))
    for _ in range(4):
        await d.step(60, **{IDOOR.replace(".", "__"): "on"})
    assert d.mem("bad").get("session_active") is True            # unchanged until the user classifies the door
    assert d.room("bad")["contact_entities"] == [WIN, IDOOR] and d.room("bad")["inside_contact_entities"] == []
    await d.finish(**{IDOOR.replace(".", "__"): "off"})


async def test_three_state_unavailable_and_missing_inside_contacts_change_nothing(hass, freezer) -> None:
    lage = "sensor.bad_innentuer_lage"
    d = await _settled(hass, freezer, _rooms(door=lage), initial={lage: ("closed", LAGE)})
    baseline = _quiet(d)
    for state in ("tilted", "open", "unavailable", "unknown", "closed"):
        for _ in range(3):
            await d.step(60, **{lage.replace(".", "__"): state})
        assert _quiet(d) == baseline, state
    d.hass.states.async_remove(lage)
    await d.step(60)
    assert _quiet(d) == baseline


async def test_cross_ventilation_follows_a_known_inside_door_and_never_from_the_door_alone(hass, freezer) -> None:
    options = {**OPTIONS, "cross_ventilation_pairs": "bad+flur"}
    # different floors: without the door no path is assumed; the connected inside door joins them while open
    d = await _settled(hass, freezer, _rooms(connected="flur", flur_floor="upper_floor"), options=options)
    await d.step(60, **{IDOOR.replace(".", "__"): "on"})
    assert d.coordinator._cross_ventilation_active() is False                     # the door alone is no airing
    for _ in range(4):
        await d.step(60, **{WIN.replace(".", "__"): "on", FLUR_WIN.replace(".", "__"): "on"})
    assert d.coordinator._cross_ventilation_active() is True                      # open door joins two open rooms
    await d.step(5, **{IDOOR.replace(".", "__"): "off"})
    assert d.coordinator._cross_ventilation_active() is False                     # closed door separates them
    await d.finish(**{WIN.replace(".", "__"): "off", FLUR_WIN.replace(".", "__"): "off"})


async def test_closed_inside_door_separates_same_floor_rooms_unless_a_doorless_opening_joins_them(hass, freezer) -> None:
    base = {**OPTIONS, "cross_ventilation_pairs": "bad+flur"}
    for options, expected in ((base, False), ({**base, "open_connections": {"bad": ["flur"]}}, True)):
        d = await _settled(hass, freezer, _rooms(connected="flur"), options=options)
        for _ in range(4):
            await d.step(60, **{WIN.replace(".", "__"): "on", FLUR_WIN.replace(".", "__"): "on"})
        assert d.coordinator._cross_ventilation_active() is expected
        await d.finish(**{WIN.replace(".", "__"): "off", FLUR_WIN.replace(".", "__"): "off"})


async def test_shared_inside_door_of_two_rooms_links_them_and_conflicts_are_reported(hass, freezer) -> None:
    shared = _rooms(flur_contacts=(FLUR_WIN, IDOOR), flur_sides={IDOOR: "inside"}, flur_floor="upper_floor")
    rooms, issues = prepare_runtime_rooms(shared)
    assert issues == [] and all(r["_inside_contacts"] == [IDOOR] for r in rooms)
    d = await _settled(hass, freezer, shared, options={**OPTIONS, "cross_ventilation_pairs": "bad+flur"})
    for _ in range(4):
        await d.step(60, **{WIN.replace(".", "__"): "on", FLUR_WIN.replace(".", "__"): "on", IDOOR.replace(".", "__"): "on"})
    assert d.coordinator._cross_ventilation_active() is True
    await d.finish(**{WIN.replace(".", "__"): "off", FLUR_WIN.replace(".", "__"): "off", IDOOR.replace(".", "__"): "off"})
    # the same contact outside in one room and inside in the other: reported, previous behaviour kept
    conflicting = _rooms(flur_contacts=(FLUR_WIN, IDOOR))
    rooms, issues = prepare_runtime_rooms(conflicting)
    assert issues == [f"contact:{IDOOR}:side_conflict:bad,flur"]
    assert all(IDOOR in r["contacts"] for r in rooms)


async def test_exhaust_fan_keeps_its_own_reason_while_an_inside_door_stands_open(hass, freezer) -> None:
    """Rule 9: the fan automation still runs; an open inside door is no opened window for it (an outside door is)."""
    from ha_tests.test_cov_setup_and_platforms import _entry, _setup, _unload
    from ha_tests.test_fan_automation_026504 import DOOR as GARAGE_DOOR, FAN, NOTIFY, START as FAN_START, _climate, _cycle, _garage, _switch
    results = {}
    for side in ("outside", "inside"):
        freezer.move_to(FAN_START)
        log: list = []
        _switch(hass, log)
        _climate(hass, garage_rh=86.0)
        hass.states.async_set(FAN, "off")
        hass.states.async_set(GARAGE_DOOR, "off", {"device_class": "door"})
        extra = {"contact_delays": {GARAGE_DOOR: 0}, **({"contact_sides": {GARAGE_DOOR: "inside"}} if side == "inside" else {})}
        entry = await _setup(hass, _entry(rooms=[_garage(**extra)], options=NOTIFY))
        coordinator = entry.runtime_data
        for _ in range(6):
            await _cycle(hass, freezer, coordinator)
        assert [s for s, _ in log] == ["turn_on"]                              # the fan starts for its own reason
        hass.states.async_set(GARAGE_DOOR, "on", {"device_class": "door"})
        for _ in range(3):
            await _cycle(hass, freezer, coordinator)
        results[side] = (coordinator.data["rooms"]["garage"]["configured_actuators"]["window_open"], [s for s, _ in log])
        hass.states.async_set(GARAGE_DOOR, "off", {"device_class": "door"})
        await _unload(hass, entry)
        hass.services.async_remove("switch", "turn_on"); hass.services.async_remove("switch", "turn_off")
    assert results["inside"] == (False, ["turn_on"])                          # fan keeps running, nothing switched off
    assert results["outside"][0] is True                                        # an outside door still counts as opened


async def test_f07_cross_ventilation_follows_the_debounced_inside_door_not_its_raw_state(hass, freezer) -> None:
    """F07: a three-state inside door moving closed → open counts after the same stable window as outside openings."""
    lage = "sensor.bad_innentuer_lage"
    options = {**OPTIONS, "cross_ventilation_pairs": "bad+flur"}
    d = await _settled(hass, freezer, _rooms(door=lage, connected="flur"), options=options, initial={lage: ("closed", LAGE)})
    for _ in range(4):
        await d.step(60, **{WIN.replace(".", "__"): "on", FLUR_WIN.replace(".", "__"): "on"})
    assert d.coordinator._cross_ventilation_active() is False                  # closed door separates the rooms
    await d.step(1, **{lage.replace(".", "__"): "open"})                        # 1 s: not yet a stable transition
    assert d.mem("bad")["inside_opening_modes"] == {lage: "closed"}
    assert d.coordinator._cross_ventilation_active() is False                  # before the fix: the raw "open" joined them
    await d.step(5)
    assert d.mem("bad")["inside_opening_modes"] == {lage: "open"} and d.coordinator._cross_ventilation_active() is True
    await d.step(60, **{lage.replace(".", "__"): "unavailable"})
    assert d.mem("bad")["inside_opening_modes"] == {lage: "open"}              # unavailable keeps the last confirmed mode
    await d.finish(**{WIN.replace(".", "__"): "off", FLUR_WIN.replace(".", "__"): "off"})


async def test_f08_a_tilted_three_state_inside_door_reaches_the_house_map_as_tilted(hass, freezer) -> None:
    """F08: the house map showed a tilted three-state inside door as 'open_unspecified' (binary mapping)."""
    from custom_components.freshairiq.house_map import live_payload
    lage = "sensor.bad_innentuer_lage"
    d = await _settled(hass, freezer, _rooms(door=lage), initial={lage: ("closed", LAGE)})
    await d.step(60, **{lage.replace(".", "__"): "tilted"})
    await d.step(10)
    d.entry.runtime_data = d.coordinator
    contact = live_payload(hass, d.entry, None)["rooms"]["bad"]["contacts"][lage]
    assert (contact["state"], contact["three_state"]) == ("tilted", True)
    assert d.mem("bad")["inside_three_state_contacts"] == [lage]
