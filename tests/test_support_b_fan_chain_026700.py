"""0.26.7.0 support case B, second chain: moisture source → fan demand → automatic control → who owns the run →
close decision → message.

Reported: "switch off the fan" although the automatic fan control was on. The chain shows: a run FreshAirIQ started
itself is ended by FreshAirIQ and the close wording never asks the user (no contradictory manual order); the run
survives a restart because the controller memory is stored; follow-up and maximum runtime end it. A fan someone else
switched on (by hand, another HA automation) stays the user's – the message now says why it is not switched off
automatically instead of a bare order.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.actuator_control import FAN_CONTROL_MOISTURE_SOURCE, decide_fan
from custom_components.freshairiq.close_wording import MANUAL_FAN_NOTE, close_instruction, fan_stop_message, house_handled_by_automation
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.notification_text import house_message

T0 = datetime(2026, 11, 11, 19, 0, tzinfo=timezone.utc)


def _decide(mem, *, fan_on, demand, now, **kw):
    return decide_fan(mode=FAN_CONTROL_MOISTURE_SOURCE, fan_on=fan_on, demand=demand, now=now, follow_up_min=10,
                      max_runtime_min=60, mem=mem, **kw)


def _room(mem, *, fan_on, aligned="Close", source=False, delta=-0.3):
    room = {"key": "bad", "name": "Badezimmer", "house_aligned_action": aligned, "moisture_source_active": source,
            "delta_g_m3": delta, "active": fan_on, "close_recommended": True,
            "configured_actuators": {"exhaust_fan": True, "exhaust_fan_control": FAN_CONTROL_MOISTURE_SOURCE,
                                     "mechanical_exhaust_active": fan_on, "window_open": False}}
    room["fan_automation"] = room_fan_automation(room, {**mem, "owned": bool(mem.get("owned"))})
    return room


def test_own_run_is_ended_by_freshairiq_and_never_asked_of_the_user():
    mem: dict = {}
    # shower starts: demand, fan off -> FreshAirIQ switches on and owns the run
    assert _decide(mem, fan_on=False, demand=True, now=T0) == "on" and mem["owned"] is True
    assert _decide(mem, fan_on=True, demand=True, now=T0 + timedelta(seconds=5), all_on=True) is None
    assert mem["command_state"] == "confirmed"
    # restart: the controller memory is stored and loaded again – the same dict decides the same way
    restored = dict(mem)
    # source over, follow-up runs (10 min): still FreshAirIQ's, nothing asked of the user
    assert _decide(restored, fan_on=True, demand=False, now=T0 + timedelta(minutes=8)) is None
    room = _room(restored, fan_on=True)
    assert room["fan_automation"]["state"] in {"follow_up", "source"}
    text = close_instruction([room])
    assert "ausschalten" not in text and "FreshAirIQ beendet die automatische Lüftung in Badezimmer" in text
    assert house_handled_by_automation("close", ["bad"], {"bad": room})
    title, _body = house_message({"kind": "close", "room_keys": ["bad"]}, {"bad": room}, True)
    assert "ausschalten" not in title
    # follow-up over -> FreshAirIQ switches off itself
    assert _decide(restored, fan_on=True, demand=False, now=T0 + timedelta(minutes=16)) == "off"


def test_maximum_runtime_ends_the_own_run():
    mem: dict = {}
    _decide(mem, fan_on=False, demand=True, now=T0)
    _decide(mem, fan_on=True, demand=True, now=T0 + timedelta(seconds=5), all_on=True)
    assert _decide(mem, fan_on=True, demand=True, now=T0 + timedelta(minutes=61)) == "off"
    assert mem["reason"] == "max_runtime"


def test_fan_switched_on_by_someone_else_stays_theirs_and_the_message_says_why():
    mem: dict = {}
    # another HA automation switched the fan on before FreshAirIQ saw the source: not FreshAirIQ's run
    assert _decide(mem, fan_on=True, demand=True, now=T0) is None and not mem.get("owned")
    room = _room(mem, fan_on=True, source=False)
    assert room["fan_automation"]["state"] == "manual"
    message = fan_stop_message(room)
    assert message.startswith(MANUAL_FAN_NOTE) and message.endswith("Lüfter ausschalten.")
    assert not house_handled_by_automation("close", ["bad"], {"bad": room})
    # FreshAirIQ never sends a switch-off for it
    assert _decide(mem, fan_on=True, demand=False, now=T0 + timedelta(minutes=30)) is None


def test_switching_off_freshairiqs_run_by_hand_is_respected_until_the_demand_ends():
    mem: dict = {}
    _decide(mem, fan_on=False, demand=True, now=T0)
    _decide(mem, fan_on=True, demand=True, now=T0 + timedelta(seconds=5), all_on=True)
    assert _decide(mem, fan_on=False, demand=True, now=T0 + timedelta(minutes=2)) is None
    assert mem["reason"] == "manual_off" and mem["blocked"] is True and not mem["owned"]
    assert _decide(mem, fan_on=False, demand=True, now=T0 + timedelta(minutes=3)) is None   # no restart while blocked
