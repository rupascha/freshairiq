"""0.26.5.4 community report: opening delay gates the reference air (A), comfort cooling tolerance (B).

A door with a 120 s opening delay that is merely passed through must neither
start a session nor switch the room to the door's reference air. Before the
fix the reference flipped immediately, the room recommendation changed and a
house push was sent although no session existed.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.freshairiq.coordinator_contacts import _delay_confirmed_modes
from custom_components.freshairiq.model import absolute_humidity
from ha_tests.test_cov_coordinator_b import (  # noqa: F401 - fixture re-export
    BERLIN, DOOR, HUM, OPTIONS, TEMP, _cleanup_coordinators, _data, _make, _room,
)

START = datetime(2026, 10, 27, 15, 50, tzinfo=BERLIN)
LAGE = {"options": ["closed", "tilted", "open"], "device_class": "enum"}
NOTIFY = {**OPTIONS, "operating_profile": "comfort", "min_duration_min": 5, "max_duration_min": 30,
          "notification_cooldown_min": 90, "notify_close": True, "notify_ventilate": True, "notify_cooling": True,
          "notification_scope": "room", "notifications_enabled": True}
DOOR_REF = (18.7, 71.0)
BASE = {
    "sensor.bad_t": (24.6, TEMP), "sensor.bad_h": (45.0, HUM), "sensor.flur_t": (24.0, TEMP), "sensor.flur_h": (44.0, HUM),
    "sensor.schlaf_t": (22.1, TEMP), "sensor.schlaf_h": (46.0, HUM),
    "sensor.badref_t": (18.8, TEMP), "sensor.badref_h": (12.6, HUM),
    "sensor.flurref_t": (DOOR_REF[0], TEMP), "sensor.flurref_h": (DOOR_REF[1], HUM),
    "binary_sensor.bad_tuer": ("off", DOOR), "binary_sensor.flur_tuer": ("off", DOOR), "binary_sensor.schlaf_fenster": ("off", DOOR),
    "binary_sensor.flur_fenster": ("off", DOOR), "sensor.flur_lage": ("closed", LAGE),
    "sensor.aussen_t": (18.8, TEMP), "sensor.aussen_h": (60.0, HUM),
}
DOOR_AH = round(absolute_humidity(*DOOR_REF), 2)


def _with_reference(room, contact, temp_entity, hum_entity, delay):
    room.setdefault("contact_delays", {})[contact] = delay
    room.setdefault("contact_reference_temperatures", {})[contact] = temp_entity
    room.setdefault("contact_reference_humidities", {})[contact] = hum_entity
    return room


def _rooms(*, flur_contacts=("binary_sensor.flur_tuer",), flur_delay=120, mode="any"):
    bad = _room("badezimmer", "Badezimmer", "ground_floor", temp=["sensor.bad_t"], hum=["sensor.bad_h"],
                contacts=["binary_sensor.bad_tuer"], volume=20)
    flur = _room("flur", "Flur", "ground_floor", temp=["sensor.flur_t"], hum=["sensor.flur_h"],
                 contacts=list(flur_contacts), volume=30, mode=mode)
    schlaf = _room("schlafzimmer", "Schlafzimmer", "upper_floor", temp=["sensor.schlaf_t"], hum=["sensor.schlaf_h"],
                   contacts=["binary_sensor.schlaf_fenster"], volume=36)
    _with_reference(bad, "binary_sensor.bad_tuer", "sensor.badref_t", "sensor.badref_h", 120)
    for contact in flur_contacts:
        _with_reference(flur, contact, "sensor.flurref_t", "sensor.flurref_h", flur_delay)
    bad.update(target_temperature_mode="manual", target_temperature=25.5)
    flur.update(target_temperature_mode="manual", target_temperature=21.9)
    return [bad, flur, schlaf]


def _record(hass, events, clock):
    for name in ("freshairiq_notification", "freshairiq_room_action", "freshairiq_room_recommendation",
                 "freshairiq_house_recommendation", "freshairiq_fan_automation"):
        hass.bus.async_listen(name, lambda e, name=name: events.append((clock["t"], name, dict(e.data))))


async def _settled(hass, freezer, rooms, options=NOTIFY, initial=None):
    d = await _make(hass, freezer, start=START, data=_data(rooms), options=options, initial={**BASE, **(initial or {})})
    for _ in range(4):
        await d.step(60)
    return d


async def test_passing_through_delayed_door_changes_nothing(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms())
    before = (d.room("flur")["action"], d.room("flur")["reference_humidity"], d.room("flur").get("reason"))
    events: list = []
    clock = {"t": "open"}
    _record(hass, events, clock)
    await d.step(4, binary_sensor__flur_tuer="on")
    during = (d.room("flur")["action"], d.room("flur")["reference_humidity"], d.room("flur").get("reason"))
    assert during == before
    assert d.mem("flur")["session_active"] is False
    clock["t"] = "closed"
    await d.step(15, binary_sensor__flur_tuer="off")
    await d.step(5)
    await d.step(60)
    assert (d.room("flur")["action"], d.room("flur")["reference_humidity"], d.room("flur").get("reason")) == before
    assert d.mem("flur")["session_active"] is False
    assert events == []


async def test_door_held_past_delay_switches_reference_and_starts_session(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms())
    default = d.room("flur")["reference_humidity"]
    assert default != DOOR_AH
    await d.step(5, binary_sensor__flur_tuer="on")
    await d.step(60)
    assert d.room("flur")["reference_humidity"] == default
    assert d.mem("flur")["session_active"] is False
    await d.step(60)
    assert d.mem("flur")["session_active"] is True
    assert d.room("flur")["reference_humidity"] == DOOR_AH


@pytest.mark.parametrize(("delay_a", "delay_b"), [(120, 0), (0, 0), (120, 120)])
async def test_shared_contact_keeps_independent_room_gates(hass, freezer, delay_a, delay_b) -> None:
    rooms = _rooms()
    shared = "binary_sensor.flur_tuer"
    rooms[0]["contacts"] = [shared]
    rooms[0]["contact_delays"] = {}
    rooms[0]["contact_reference_temperatures"] = {}
    rooms[0]["contact_reference_humidities"] = {}
    _with_reference(rooms[0], shared, "sensor.flurref_t", "sensor.flurref_h", delay_a)
    rooms[1]["contact_delays"] = {shared: delay_b}
    d = await _settled(hass, freezer, rooms)
    defaults = {k: d.room(k)["reference_humidity"] for k in ("badezimmer", "flur")}
    await d.step(30, binary_sensor__flur_tuer="on")
    for key, delay in (("badezimmer", delay_a), ("flur", delay_b)):
        assert d.mem(key)["session_active"] is (delay == 0)
        assert d.room(key)["reference_humidity"] == (DOOR_AH if delay == 0 else defaults[key])
    await d.step(95)
    await d.step(30)
    for key in ("badezimmer", "flur"):
        assert d.mem(key)["session_active"] is True
        assert d.room(key)["reference_humidity"] == DOOR_AH


@pytest.mark.parametrize("mode", ["any", "all"])
async def test_several_contacts_any_and_all_respect_delay(hass, freezer, mode) -> None:
    rooms = _rooms(flur_contacts=("binary_sensor.flur_tuer", "binary_sensor.flur_fenster"), mode=mode)
    d = await _settled(hass, freezer, rooms)
    default = d.room("flur")["reference_humidity"]
    await d.step(30, binary_sensor__flur_tuer="on", binary_sensor__flur_fenster="on")
    assert d.room("flur")["reference_humidity"] == default
    assert d.mem("flur")["session_active"] is False
    await d.step(95)
    await d.step(30)
    assert d.mem("flur")["session_active"] is True
    assert d.room("flur")["reference_humidity"] == DOOR_AH


async def test_three_state_contact_uses_its_stable_age(hass, freezer) -> None:
    d = await _settled(hass, freezer, _rooms(flur_contacts=("sensor.flur_lage",)))
    default = d.room("flur")["reference_humidity"]
    await d.step(30, sensor__flur_lage=("tilted", LAGE))
    await d.step(30)
    assert d.room("flur")["reference_humidity"] == default
    assert d.mem("flur")["session_active"] is False
    await d.step(30, sensor__flur_lage=("closed", LAGE))
    await d.step(30)
    assert d.room("flur")["reference_humidity"] == default
    await d.step(30, sensor__flur_lage=("tilted", LAGE))
    for _ in range(5):
        await d.step(30)
    assert d.mem("flur")["session_active"] is True
    assert d.room("flur")["reference_humidity"] == DOOR_AH


async def test_reopen_in_running_session_keeps_immediate_reference(hass, freezer) -> None:
    rooms = _rooms(flur_contacts=("binary_sensor.flur_tuer", "binary_sensor.flur_fenster"))
    rooms[1]["contact_delays"]["binary_sensor.flur_fenster"] = 0
    rooms[1]["contact_reference_temperatures"].pop("binary_sensor.flur_fenster")
    rooms[1]["contact_reference_humidities"].pop("binary_sensor.flur_fenster")
    d = await _settled(hass, freezer, rooms)
    default = d.room("flur")["reference_humidity"]
    await d.step(30, binary_sensor__flur_fenster="on")
    assert d.mem("flur")["session_active"] is True
    assert d.room("flur")["reference_humidity"] == default
    # Expectation corrected in 0.26.5.5 (F03, audit 29.10.): this test asserted that a door opened
    # for the first time during a window airing counts at once – that skipped the door's own
    # 120 s delay. The re-open rule applies only to openings the running session already counted.
    await d.step(10, binary_sensor__flur_tuer="on")
    assert d.room("flur")["reference_humidity"] == default
    await d.step(60)
    assert d.room("flur")["reference_humidity"] == default  # 70 s: still inside the delay
    await d.step(60)
    assert d.room("flur")["reference_humidity"] == DOOR_AH  # past its delay: counted
    # once counted, closing and re-opening it within the same session counts at once
    await d.step(10, binary_sensor__flur_tuer="off")
    assert d.room("flur")["reference_humidity"] == default
    await d.step(10, binary_sensor__flur_tuer="on")
    assert d.room("flur")["reference_humidity"] == DOOR_AH


async def test_running_exhaust_fan_unaffected_by_passing_door(hass, freezer) -> None:
    rooms = _rooms()
    rooms[0]["exhaust_fan"] = "fan.bad_abluft"
    d = await _settled(hass, freezer, rooms, initial={"fan.bad_abluft": ("on", {})})
    assert d.mem("badezimmer")["session_active"] is True
    before = {k: (d.room(k)["action"], d.room(k)["reference_humidity"]) for k in ("flur", "schlafzimmer")}
    events: list = []
    clock = {"t": "pass"}
    _record(hass, events, clock)
    await d.step(4, binary_sensor__flur_tuer="on")
    await d.step(15, binary_sensor__flur_tuer="off")
    await d.step(5)
    assert d.mem("badezimmer")["session_active"] is True
    assert {k: (d.room(k)["action"], d.room(k)["reference_humidity"]) for k in ("flur", "schlafzimmer")} == before
    assert not [e for e in events if e[1] == "freshairiq_fan_automation"]
    assert not [e for e in events if e[2].get("room_key") == "flur"]


async def test_delay_confirmed_modes_unit(hass) -> None:
    room = {"contact_delays": {"binary_sensor.a": 120}, "contact_delay": 0}
    now = datetime(2026, 10, 27, 15, 0, tzinfo=BERLIN)
    modes = {"binary_sensor.a": "open", "binary_sensor.b": "tilted", "binary_sensor.c": "closed"}
    # No HA state and no stable timestamp: the opening is not proven yet.
    assert _delay_confirmed_modes(hass, room, now, modes) == {
        "binary_sensor.a": "closed", "binary_sensor.b": "closed", "binary_sensor.c": "closed"}
    since = {"binary_sensor.a": now.replace(minute=0, second=0), "binary_sensor.b": now}
    assert _delay_confirmed_modes(hass, room, now.replace(minute=1, second=0), modes, contact_since=since) == {
        "binary_sensor.a": "closed", "binary_sensor.b": "tilted", "binary_sensor.c": "closed"}
    assert _delay_confirmed_modes(hass, room, now.replace(minute=2, second=0), modes, contact_since=since)["binary_sensor.a"] == "open"
    assert _delay_confirmed_modes(hass, room, now, modes, session_active=True) == modes


async def test_bedroom_comfort_cooling_end_to_end(hass, freezer) -> None:
    """Comfort cooling through the real coordinator: tilted three-state window with its own reference pair."""
    rooms = _rooms()
    lage = "sensor.schlaf_lage"
    rooms[2]["contacts"] = [lage]
    rooms[2]["contact_delays"] = {}
    _with_reference(rooms[2], lage, "sensor.schlafref_t", "sensor.schlafref_h", 120)
    rooms[2].update(target_temperature_mode="manual", target_temperature=19.0)
    room_ah = absolute_humidity(22.1, 46.0)
    ref_rh = next(rh / 10 for rh in range(1000) if absolute_humidity(18.6, rh / 10) >= room_ah + 0.28)
    d = await _settled(hass, freezer, rooms, initial={
        lage: ("closed", LAGE), "sensor.schlafref_t": (18.6, TEMP), "sensor.schlafref_h": (ref_rh, HUM)})
    events: list = []
    clock = {"t": "run"}
    _record(hass, events, clock)
    await d.step(5, **{lage.replace(".", "__"): ("tilted", LAGE)})
    for _ in range(80):
        await d.step(60)
    assert d.mem("schlafzimmer")["session_active"] is True
    room = d.room("schlafzimmer")
    assert -5 <= room["moisture_effect_next_5_min_ml"] < 0
    assert room["action"] == "Continue ventilating"
    assert room["comfort_cooling_active"] is True
    assert room["house_aligned_action"] != "close"
    assert not [e for e in events if e[1] == "freshairiq_notification" and e[2].get("room_key") == "schlafzimmer"
                and e[2].get("type") == "close"]
