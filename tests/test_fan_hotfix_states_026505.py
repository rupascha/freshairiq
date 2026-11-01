"""0.26.5.5 hotfix: fan states and wording (pure); the full chain runs in ha_tests/test_fan_hotfix_026505.py.

F3  goal reached, switch-off not sent yet → "stop_check"; sent and not reported → "stopping";
    a fan without a state after the switch-off → never "completed"; failed → "failed_off".
F4  a group start where only part came on is retried once (only while the demand lasts);
    a group partly switched on by hand is never taken over.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S, decide_fan
from custom_components.freshairiq.close_wording import fan_stop_message
from custom_components.freshairiq.fan_automation import auto_stop, event_fields, room_fan_automation
from custom_components.freshairiq.localize import to_english as translate_text

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def _decide(mem, *, fan_on=True, all_on=False, demand=True, now=NOW):
    return decide_fan(mode="recommendation", fan_on=fan_on, demand=demand, now=now, follow_up_min=10, max_runtime_min=60,
                      mem=mem, off_confirm_s=30.0, all_on=all_on, all_off=False if fan_on else True)


def test_f4_a_partial_start_is_retried_once_then_reported() -> None:
    mem: dict = {}
    assert _decide(mem, fan_on=False, all_on=False) == "on" and mem["owned"]
    later = NOW + timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1)
    assert _decide(mem, now=later) == "on"  # one more try for the fan that did not come on
    assert mem["command_state"] == "pending" and mem["group_retry"] and mem["owned"]
    again = later + timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1)
    assert _decide(mem, now=again) is None
    assert (mem["command_state"], mem["reason"]) == ("partial", "partial_start") and mem["owned"]
    # a new airing starts the count again
    mem.update(owned=False, command="off", command_state="confirmed")
    assert _decide(mem, fan_on=False, now=again + timedelta(hours=1)) == "on" and "group_retry" not in mem


def test_f4_no_retry_without_demand() -> None:
    mem = {"owned": True, "since": NOW.isoformat(), "command": "on", "command_state": "pending", "command_at": NOW.isoformat()}
    later = NOW + timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1)
    assert _decide(mem, demand=False, now=later) is None and mem["command_state"] == "partial"


def test_f4_a_group_switched_on_by_hand_is_not_taken_over() -> None:
    mem: dict = {}
    for step in range(4):
        assert _decide(mem, now=NOW + timedelta(minutes=step)) is None
    assert not mem.get("owned")


def _room(snap, *, fan_on=True, aligned="close", mode="recommendation", fans=("switch.a", "switch.b")):
    room = {"configured_actuators": {"exhaust_fan_control": mode, "exhaust_fan": list(fans), "mechanical_exhaust_active": fan_on},
            "house_aligned_action": aligned, "delta_g_m3": 0.2}
    room["fan_automation"] = room_fan_automation(room, snap)
    return room


@pytest.mark.parametrize(("snap", "fan_on", "state", "label_key", "user"), [
    ({"owned": True, "command": "on", "command_state": "confirmed"}, True, "stopping", "stop_check", False),
    ({"owned": True, "command": "on", "command_state": "partial", "fans_total": 2, "fans_on": 1}, True, "stopping", "stop_check", False),
    ({"owned": False, "command": "off", "command_state": "pending"}, True, "stopping", "stopping", False),
    ({"owned": False, "command": "off", "command_state": "pending", "fans_unknown": 1, "fans_total": 2, "fans_on": 0}, False, "stopping", "stopping", False),
    ({"owned": False, "command": "off", "command_state": "failed", "fans_unknown": 1, "fans_total": 2, "fans_on": 0}, False, "failed", "failed_off", True),
    ({"owned": False, "command": "off", "command_state": "failed"}, True, "failed", "failed_off", True),
    ({"owned": False, "command": "off", "command_state": "pending"}, False, "completed", None, False),
    ({"owned": False, "command": "off", "command_state": "confirmed"}, False, "completed", None, False),
    ({"owned": False, "command": None, "command_state": None}, True, "manual", None, True),
    ({"owned": True, "shared_for": True}, True, "shared", "shared_for", False),
    ({"external_lock": True}, True, "external", "external", False),
])
def test_f3_every_phase_of_a_switch_off_has_its_own_state(snap, fan_on, state, label_key, user) -> None:
    value = _room(snap, fan_on=fan_on)["fan_automation"]
    assert (value["state"], value["label_key"], value["user_action_needed"]) == (state, label_key, user)


def test_f3_push_and_english_wording_match_the_phase() -> None:
    checking = _room({"owned": True, "command": "on", "command_state": "confirmed"})
    sent = _room({"owned": False, "command": "off", "command_state": "pending"})
    assert auto_stop(checking) and auto_stop(sent)
    assert fan_stop_message(checking) == "Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus."
    assert fan_stop_message(sent) == "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung."
    assert translate_text(fan_stop_message(checking)) == "Airing goal reached – FreshAirIQ checks briefly and then ends the airing."
    assert translate_text(checking["fan_automation"]["label"]) == "Airing goal reached – FreshAirIQ checks briefly and then ends the airing"
    # the event contract keeps its keys
    assert set(event_fields(checking)) == {"mode", "state", "owned", "command", "command_state", "user_action_needed"}
