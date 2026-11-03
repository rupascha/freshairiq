"""0.26.5.5 (02.11.): exhaust fan lock period and window/door per contact (pure parts)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.freshairiq.actuator_control import clock_minutes, fan_block_active
from custom_components.freshairiq.close_wording import close_instruction, opening_kind
from custom_components.freshairiq.fan_automation import auto_start, auto_stop, handled_label, room_fan_automation
from custom_components.freshairiq.house_autolayout import _openings
from custom_components.freshairiq.recommendation import build_recommendation

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.mark.parametrize(("value", "minutes"), [("22:00", 1320), ("07:05:00", 425), ("0:0", 0), ("24:00", None), ("7", None),
                                                (None, None), ("ab:cd", None), ("12:60", None)])
def test_clock_minutes(value, minutes) -> None:
    assert clock_minutes(value) == minutes


@pytest.mark.parametrize(("start", "end", "hhmm", "active"), [
    ("22:00", "07:00", (23, 30), True), ("22:00", "07:00", (2, 0), True), ("22:00", "07:00", (7, 0), False),
    ("22:00", "07:00", (21, 59), False), ("09:00", "17:00", (12, 0), True), ("09:00", "17:00", (17, 0), False),
    ("09:00", "09:00", (9, 0), False), (None, "07:00", (2, 0), False), ("22:00", None, (23, 0), False)])
def test_lock_period_over_midnight_and_off_without_both_times(start, end, hhmm, active) -> None:
    assert fan_block_active(start, end, datetime(2026, 11, 2, *hhmm, tzinfo=BERLIN)) is active


def test_lock_period_follows_the_wall_clock_over_the_time_change() -> None:
    # 25.10.2026: winter time begins at 03:00 → 02:00 (Berlin); 29.03.2026: summer time 02:00 → 03:00
    assert fan_block_active("01:30", "02:30", datetime(2026, 10, 25, 2, 15, tzinfo=BERLIN, fold=1))
    assert not fan_block_active("01:30", "02:30", datetime(2026, 3, 29, 3, 15, tzinfo=BERLIN))


def _room(**extra):
    room = {"house_aligned_action": "ventilate",
            "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": ["switch.f"], "mechanical_exhaust_active": False}}
    room.update(extra)
    return room


def test_status_during_the_lock_period() -> None:
    off = room_fan_automation(_room(), {"block_time": True, "owned": False})
    assert (off["state"], off["label"], off["user_action_needed"]) == ("blocked_time", "Ablüfter wegen eingestellter Sperrzeit ausgeschaltet", False)
    room = {**_room(), "fan_automation": off}
    assert auto_start(room) and auto_stop(room)  # no "switch the fan on/off" request for the user
    assert handled_label(room, "ventilate", "en") == "Exhaust fan switched off because of the set lock period"
    on_room = _room(configured_actuators={"exhaust_fan_control": "recommendation", "exhaust_fan": ["switch.f"], "mechanical_exhaust_active": True})
    stopping = room_fan_automation(on_room, {"block_time": True, "owned": False, "command": "off", "command_state": "pending"})
    assert (stopping["state"], stopping["label_key"]) == ("stopping", "block_time")
    manual = room_fan_automation(on_room, {"block_time": True, "owned": False})
    assert manual["state"] == "manual"  # switched on by hand during the lock period: the user's, nothing is said for FreshAirIQ
    assert room_fan_automation(_room(), {"block_time": False})["state"] == "recommended"


def _kinds(*pairs):
    return {"name": "Bad", "contact_entities": [c for c, _ in pairs], "contact_kinds": {c: k for c, k in pairs if k}}


def test_opening_kind_needs_every_contact_stated_alike() -> None:
    assert opening_kind(_kinds(("a", "window"), ("b", "window"))) == "window"
    assert opening_kind(_kinds(("a", "door"))) == "door"
    assert opening_kind(_kinds(("a", "window"), ("b", "door"))) is None
    assert opening_kind(_kinds(("a", "window"), ("b", None))) is None  # one not stated: no assumption
    assert opening_kind({"name": "Bad", "contact_entities": ["a"]}) is None  # older setup without the field
    assert opening_kind({"name": "x"}) is None and opening_kind(None) is None


def test_close_wording_with_and_without_kinds() -> None:
    bad = {**_kinds(("binary_sensor.b", "window")), "name": "Bad"}
    flur = {**_kinds(("binary_sensor.f", "door")), "name": "Flur"}
    kueche = {"name": "Küche", "contact_entities": ["binary_sensor.k"]}
    assert close_instruction([bad]) == "Fenster in Bad schließen"
    assert close_instruction([flur]) == "Tür in Flur schließen"
    assert close_instruction([flur, {**flur, "name": "Diele"}]) == "Türen in Flur + Diele schließen"
    assert close_instruction([kueche]) == "Küche schließen"  # unchanged without a kind
    assert close_instruction([bad, flur]) == "Bad + Flur schließen"  # mixed kinds: the names as before


def test_the_house_map_proposal_draws_a_door_contact_as_an_outside_door() -> None:
    rooms = [{"key": "flur", "contacts": ["binary_sensor.haustuer", "binary_sensor.fenster"], "contact_kinds": {"binary_sensor.haustuer": "door"}}]
    openings = _openings(rooms, {"flur": [[0, 0], [4, 0], [4, 3], [0, 3]]}, {})
    kinds = {o["contacts"][0]: (o["kind"], o["mechanics"]) for o in openings}
    assert kinds == {"binary_sensor.haustuer": ("door", "door"), "binary_sensor.fenster": ("window", "unknown")}


def test_open_instruction_names_windows_or_doors_only_when_stated() -> None:
    from tests.test_recommendation import base_options, room  # noqa: PLC0415 – the established room fixture

    def instruction(**kinds):
        extra = {"contact_entities": ["binary_sensor.c"], **({"contact_kinds": {"binary_sensor.c": kinds["kind"]}} if kinds else {})}
        rooms = {"bed": room("bed", "Schlafzimmer", action="Ventilate", humidity=70, potential_ml=130, delta_g_m3=2.4, **extra)}
        return build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=130, recommended_duration_min=8)["instruction"]

    assert instruction(kind="window") == "Fenster in Schlafzimmer öffnen · ca. 8 min"
    assert instruction(kind="door") == "Tür in Schlafzimmer öffnen · ca. 8 min"
    assert instruction() == "Schlafzimmer: c öffnen · ca. 8 min"  # not stated: as before
    rooms = {k: room(k, n, action="Ventilate", humidity=70, potential_ml=130, delta_g_m3=2.4, contact_entities=[f"binary_sensor.{k}"],
                     contact_kinds={f"binary_sensor.{k}": "door"}) for k, n in (("a", "Flur"), ("b", "Diele"))}
    assert build_recommendation(rooms, base_options(), threshold_ml=100, total_potential_ml=260, recommended_duration_min=8)["instruction"].startswith("Türen in ")
