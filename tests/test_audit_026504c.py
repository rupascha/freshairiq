"""0.26.5.4: consolidated audit of the 0.26.5.4 artefact (S01, S02, S06, S08, S12, S19).

* S01  a close remembered earlier (``close_notified``) won over CO2 needing the air again.
* S02  "off + unavailable" confirmed a fan group as switched off.
* S06  Node-RED never heard that the automatic fan went from requested to running or
       failed while the room action stayed "ventilate".
* S08  a partly started fan group was shown as "automatic airing is running".
* S12  "Fenster 1" -> "Fenster 2" was taken for the same house instruction.
* S19  a room removed and added again under the same key replayed its old action.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.actuator_control import (
    FAN_COMMAND_TIMEOUT_S, FAN_CONTROL_RECOMMENDATION, decide_fan, settle_removed_off,
)
from custom_components.freshairiq.automation_events import (
    EVENT_FAN_AUTOMATION, EVENT_ROOM_ACTION, AutomationEventEmitter, house_signature, room_payload,
)
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400}
T0 = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- S01

def _room(**extra) -> RoomInput:
    values = dict(key="wz", name="Wohnzimmer", temperature=22.0, humidity=50.0, reference_temperature=22.0, reference_humidity=50.0,
                  volume_m3=30.0, contact_open=True, contact_open_seconds=1020, learning_rate=0.03, session_active=True,
                  session_elapsed_min=17.0, session_fresh_measurements=3, session_target_min=30.0,
                  session_start_ah=absolute_humidity(22.0, 51.0), session_start_temp=22.0, close_notified=True)
    values.update(extra)
    return RoomInput(**values)


@pytest.mark.parametrize("co2", [1100, 1450])
def test_co2_needing_the_air_again_lifts_an_earlier_close(co2) -> None:
    result = evaluate_room(_room(co2=co2, co2_lead_latched=True), OPTIONS, False)
    assert result.action == "Continue ventilating" and result.close_recommended is False


def test_the_close_returns_once_co2_is_down_and_protection_still_closes() -> None:
    assert evaluate_room(_room(co2=900), OPTIONS, False).action == "Close"
    assert evaluate_room(_room(co2=None), OPTIONS, False).action == "Close"  # CO2 goal off: the remembered close holds
    # the maximum airing duration still ends it with CO2 above the warning threshold
    assert evaluate_room(_room(co2=1100, co2_lead_latched=True, session_elapsed_min=41.0, contact_open_seconds=2460), OPTIONS, False).action == "Close"


# --------------------------------------------------------------------------- S02

def _decide(mem, *, fan_on, seconds, all_off=None, demand=False):
    return decide_fan(mode=FAN_CONTROL_RECOMMENDATION, fan_on=fan_on, demand=demand, now=T0 + timedelta(seconds=seconds),
                      follow_up_min=10, max_runtime_min=60, mem=mem, all_off=all_off)


def test_off_plus_unavailable_is_no_confirmed_switch_off() -> None:
    mem = {"command": "off", "command_state": "pending", "command_at": T0.isoformat()}
    _decide(mem, fan_on=False, all_off=False, seconds=5)
    assert mem["command_state"] == "pending"
    _decide(mem, fan_on=False, all_off=False, seconds=FAN_COMMAND_TIMEOUT_S + 1)
    assert mem["command_state"] == "failed"
    every = {"command": "off", "command_state": "pending", "command_at": T0.isoformat()}
    _decide(every, fan_on=False, all_off=True, seconds=5)
    assert every["command_state"] == "confirmed"


def test_the_removed_control_switch_off_needs_every_fan_off() -> None:
    sent = {"reason": "control_removed", "command": "off", "command_state": "pending", "command_at": T0.isoformat()}
    assert settle_removed_off(dict(sent), False, T0 + timedelta(seconds=5), all_off=False) is False
    done = dict(sent)
    assert settle_removed_off(done, False, T0 + timedelta(seconds=5), all_off=True) is True and done["command_state"] == "confirmed"


# --------------------------------------------------------------------------- S08

def _fan_room(**extra) -> dict:
    room = {"key": "bad", "name": "Bad", "action": "Ventilate", "house_aligned_action": "ventilate", "active": False, "data_quality": "ok",
            "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": True, "mechanical_exhaust_active": True}}
    room.update(extra)
    return room


@pytest.mark.parametrize(("on", "partial"), [(1, True), (2, False)])
def test_a_partly_started_group_is_shown_and_asks_the_user(on, partial) -> None:
    snap = {"owned": True, "command": "on", "command_state": "partial" if on == 1 else "confirmed", "fans_total": 2, "fans_on": on}
    value = room_fan_automation(_fan_room(), snap)
    assert (value["state"] == "partial") is partial and value["user_action_needed"] is partial
    if partial:
        assert value["label"] == "Nicht alle Ablüfter sind angesprungen – bitte die übrigen prüfen"
        payload = room_payload({**_fan_room(), "fan_automation": value}, previous_action=None, language="en", entry_id="e")
        assert payload["category"] == "action" and payload["action_label"] == "Not every exhaust fan came on – please check the others"
    else:
        assert value["state"] == "running" and value["label"] == "Automatische Lüftung läuft"


def test_a_partial_group_that_is_being_stopped_says_so() -> None:
    snap = {"owned": True, "command": "on", "command_state": "partial", "fans_total": 2, "fans_on": 1}
    assert room_fan_automation(_fan_room(house_aligned_action="close"), snap)["state"] == "stopping"


# --------------------------------------------------------------------------- S06

def _cycle(emitter, *rooms, iq=None):
    return emitter.process({"rooms": {r["key"]: r for r in rooms}, "intelligent_recommendation": iq or {"kind": "okay", "instruction": ""}})


def _with_fan(state: str, command_state: str, must_act: bool, label_key: str | None = None) -> dict:
    return _fan_room(fan_automation={"mode": "recommendation", "state": state, "owned": state != "failed", "command": "on",
                                     "command_state": command_state, "user_action_needed": must_act, "label_key": label_key})


def test_a_fan_status_change_fires_its_own_event_while_the_room_action_stays() -> None:
    fired: list = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    _cycle(emitter, _with_fan("requested", "pending", False, "requested"))  # first cycle: silent
    assert fired == []
    _cycle(emitter, _with_fan("running", "confirmed", False, "running"))
    _cycle(emitter, _with_fan("running", "confirmed", False, "running"))  # unchanged: nothing
    _cycle(emitter, _with_fan("failed", "failed", True, "failed_on"))
    assert [t for t, _ in fired] == [EVENT_FAN_AUTOMATION, EVENT_FAN_AUTOMATION]
    running, failed = fired[0][1], fired[1][1]
    assert (running["previous_state"], running["state"], running["category"], running["action"]) == ("requested", "running", "status", "ventilate")
    assert running["message"] == "Bad: Automatische Lüftung läuft."
    assert (failed["state"], failed["user_action_needed"], failed["category"]) == ("failed", True, "action")
    assert failed["label"].startswith("Ablüfter konnte nicht automatisch eingeschaltet werden")
    assert failed["schema_version"] == 1 and "entity_id" not in str(failed)


def test_no_fan_event_for_a_room_without_automatic_fan() -> None:
    fired: list = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    plain = {"key": "wz", "name": "Wohnzimmer", "action": "Okay", "house_aligned_action": "okay", "data_quality": "ok"}
    for _ in range(3):
        _cycle(emitter, plain)
    _cycle(emitter, plain | {"fan_automation": {"state": "running", "command_state": "confirmed", "user_action_needed": False}})  # control switched on later
    assert fired == []


# --------------------------------------------------------------------------- S12

def test_a_different_opening_is_a_new_house_instruction_the_countdown_is_not() -> None:
    first = house_signature({"kind": "continue", "room_keys": ["bad"], "instruction": "Bad Fenster 1 offen lassen · noch ca. 19 min"})
    countdown = house_signature({"kind": "continue", "room_keys": ["bad"], "instruction": "Bad Fenster 1 offen lassen · noch ca. 18 min"})
    other = house_signature({"kind": "continue", "room_keys": ["bad"], "instruction": "Bad Fenster 2 offen lassen · noch ca. 18 min"})
    english = house_signature({"kind": "continue", "room_keys": ["bad"], "instruction": "Keep window 1 open · about 7 minutes left"})
    assert first == countdown and first != other
    assert english == house_signature({"kind": "continue", "room_keys": ["bad"], "instruction": "Keep window 1 open · about 6 minutes left"})


# --------------------------------------------------------------------------- S19

def test_a_room_added_again_under_the_same_key_starts_silently() -> None:
    fired: list = []
    emitter = AutomationEventEmitter(lambda t, p: fired.append((t, p)), "entry1")
    bad = {"key": "bad", "name": "Bad", "action": "Close", "house_aligned_action": "close", "data_quality": "ok"}
    _cycle(emitter, bad)
    _cycle(emitter)  # room removed
    _cycle(emitter, {**bad, "action": "Ventilate", "house_aligned_action": "ventilate"})  # added again: first appearance
    assert fired == []
    _cycle(emitter, {**bad, "action": "Close", "house_aligned_action": "close"})
    assert [t for t, _ in fired].count(EVENT_ROOM_ACTION) == 1 and fired[0][1]["previous_action"] == "ventilate"


def test_a_partly_started_group_is_pushed_as_a_task_with_reminders() -> None:
    from custom_components.freshairiq.notification_policy import _automatic, auto_room_event

    snap = {"owned": True, "command": "on", "command_state": "partial", "fans_total": 2, "fans_on": 1}
    partial = {**_fan_room(), "fan_automation": room_fan_automation(_fan_room(), snap)}
    event, _title, message = auto_room_event("ventilate", partial, "Jetzt lüften.")
    assert (event, message) == ("ventilate", "Nicht alle Ablüfter sind angesprungen – bitte die übrigen prüfen.")
    assert _automatic("Ventilate", partial) is False  # the user is reminded like for any task
    running = {**_fan_room(), "fan_automation": room_fan_automation(_fan_room(), {**snap, "command_state": "confirmed", "fans_on": 2})}
    assert auto_room_event("ventilate", running, "Jetzt lüften.")[0] == "fan_auto" and _automatic("Ventilate", running) is True


# --------------------------------------------------------------------------- N04 (audit of the 0.26.5.4(4) artefact)

@pytest.mark.parametrize(("co2", "action"), [(1450, "Continue ventilating"), (1100, "Continue ventilating"), (900, "Close")])
def test_co2_keeps_a_fan_only_airing_running(co2, action) -> None:
    room = _room(co2=co2, co2_lead_latched=co2 >= 1000, mechanical_only=True)  # the running fan is the open airing
    assert evaluate_room(room, OPTIONS, False).action == action


def test_fan_failing_to_go_off_asks_the_user() -> None:
    value = room_fan_automation(_fan_room(), {"owned": True, "command": "on", "command_state": "confirmed", "own_off": "failed"})
    assert value["state"] == "failed" and value["user_action_needed"] is True
    assert value["label"] == "Ablüfter konnte nicht automatisch ausgeschaltet werden – bitte von Hand ausschalten"
