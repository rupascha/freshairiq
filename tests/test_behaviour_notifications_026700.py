"""0.26.7.0 point 4: behaviour learning adapts the reminders – conservatively and with evidence.

Adapted (only with ≥ 12 episodes somebody could act on): reminder timing (not before the household usually reacts),
frequency and repetition (doubled interval, at most two reminders) and summarising (one message for several rooms).
Never adapted: the first message of an action, protection, critical CO₂, critical surface humidity / mould, rooms
whose following cannot be observed (no contact), with personalisation switched off or reminders off. A reminder held
back in the night window does not use up the limit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.intelligence import ensure_behaviour_defaults, sync_active_recommendation
from custom_components.freshairiq.notification_adaptation import (
    MAX_ADAPTED_REMINDERS, MIN_ACTIONABLE_SAMPLES, REASON_DISABLED, REASON_FEW_SAMPLES, REASON_FEWER,
    REASON_INCONSISTENT, REASON_LATER, REASON_NO_CONTACT, REASON_NO_REMINDERS, REASON_PROTECTED, REASON_UNCHANGED,
    notification_adaptation,
)
from custom_components.freshairiq.notification_policy import REMINDERS_SENT, room_notification_events
from custom_components.freshairiq.notification_text import room_messages

T0 = datetime(2026, 11, 13, 17, 0, tzinfo=timezone.utc)
OPTIONS = {"action_reminder_min": 10, "personalisation_enabled": True, "co2_critical": 1400,
           "notify_close": True, "notify_ventilate": True}


def _room(key="bad", *, actionable=20, followed=2, streak=0, delay=None, delay_samples=0, **extra):
    room = {"key": key, "name": key.title(), "action": "Close", "active": True, "data_quality": "ok", "contact_count": 1,
            "behaviour_actionable": actionable, "behaviour_actionable_followed": followed, "behaviour_ignored_streak": streak,
            "behaviour_avg_follow_delay_min": delay, "behaviour_follow_delay_samples": delay_samples,
            "goal_state": {"hard_close": False, "goals": []}, "surface_rh": 60, "co2": 600, "mould_level": "Low"}
    room.update(extra)
    return room


# --------------------------------------------------------------------------------------------------- the rule

def test_low_follow_rate_doubles_the_interval_limits_and_summarises():
    adapt = notification_adaptation(_room(), OPTIONS, 10.0)
    assert adapt["active"] and adapt["reason"] == REASON_FEWER
    assert adapt["reminder_interval_min"] == 20.0 and adapt["max_reminders"] == MAX_ADAPTED_REMINDERS and adapt["summarize"]
    assert adapt["follow_rate_pct"] == 10.0 and adapt["samples"] == 20
    assert notification_adaptation(_room(), OPTIONS, 45.0)["reminder_interval_min"] == 60.0   # never above 60 min
    streak = notification_adaptation(_room(followed=15, streak=6), OPTIONS, 10.0)
    assert streak["active"] and streak["max_reminders"] == 2


def test_a_late_but_reliable_household_is_reminded_later_not_less():
    adapt = notification_adaptation(_room(followed=18, delay=24.0, delay_samples=8), OPTIONS, 10.0)
    assert adapt["active"] and adapt["reason"] == REASON_LATER
    assert adapt["reminder_interval_min"] == 30.0 and adapt["max_reminders"] is None and not adapt["summarize"]
    few_delays = notification_adaptation(_room(followed=18, delay=24.0, delay_samples=3), OPTIONS, 10.0)
    assert not few_delays["active"] and few_delays["reason"] == REASON_UNCHANGED


def test_good_follow_rate_changes_nothing():
    adapt = notification_adaptation(_room(followed=16), OPTIONS, 10.0)
    assert not adapt["active"] and adapt["reminder_interval_min"] == 10.0 and adapt["max_reminders"] is None


@pytest.mark.parametrize(("room", "options", "base", "reason"), [
    (_room(actionable=MIN_ACTIONABLE_SAMPLES - 1, followed=0), OPTIONS, 10.0, REASON_FEW_SAMPLES),
    (_room(), {**OPTIONS, "personalisation_enabled": False}, 10.0, REASON_DISABLED),
    (_room(), OPTIONS, None, REASON_NO_REMINDERS),
    (_room(followed=25), OPTIONS, 10.0, REASON_INCONSISTENT),          # more followed than possible
    (_room(actionable=-3, followed=0), OPTIONS, 10.0, REASON_INCONSISTENT),
    (_room(actionable="x", followed=0), OPTIONS, 10.0, REASON_INCONSISTENT),
    (_room(actionable=20.5, followed=0), OPTIONS, 10.0, REASON_INCONSISTENT),
    (_room(contact_count=0), OPTIONS, 10.0, REASON_NO_CONTACT),         # following cannot be seen
    (_room(goal_state={"hard_close": True}), OPTIONS, 10.0, REASON_PROTECTED),
    (_room(co2=1500), OPTIONS, 10.0, REASON_PROTECTED),
    (_room(surface_rh=92), OPTIONS, 10.0, REASON_PROTECTED),
    (_room(mould_level="High"), OPTIONS, 10.0, REASON_PROTECTED),
])
def test_never_adapted(room, options, base, reason):
    adapt = notification_adaptation(room, options, base)
    assert not adapt["active"] and adapt["reason"] == reason
    assert adapt["max_reminders"] is None and not adapt["summarize"] and adapt["reminder_interval_min"] == base


# --------------------------------------------------------------------------------------------------- the cycle

class _Store:
    def __init__(self):
        self.data: dict = {"rooms": {}}

    def room(self, key):
        return self.data["rooms"].setdefault(key, {})


def _cycle(store, rooms, minute, options=OPTIONS, quiet=False):
    events, _ = room_notification_events(rooms, store, T0 + timedelta(minutes=minute), options, None,
                                         sensor_alerts=lambda room: False, quiet=quiet)
    return events


def test_first_message_is_never_held_back_and_reminders_stop_after_two():
    store, rooms = _Store(), {"bad": _room()}
    assert [r["key"] for r in _cycle(store, rooms, 0)["Close"]] == ["bad"]          # the recommendation itself
    reminders = [minute for minute in range(1, 200) if _cycle(store, rooms, minute)["reminder"]]
    assert reminders == [20, 40]                                                     # doubled interval, at most two
    assert rooms["bad"]["notification_adaptation"]["reason"] == REASON_FEWER         # traceable on the room
    rooms["bad"]["action"] = "Ventilate"; rooms["bad"]["active"] = False
    assert _cycle(store, rooms, 201)["Ventilate"]                                    # a new action is announced
    assert store.room("bad")[REMINDERS_SENT] == 0


def test_without_adaptation_reminders_repeat_as_before():
    store, rooms = _Store(), {"bad": _room(followed=16)}
    _cycle(store, rooms, 0)
    assert [m for m in range(1, 61) if _cycle(store, rooms, m)["reminder"]] == [10, 20, 30, 40, 50, 60]


def test_protection_keeps_its_reminders():
    store, rooms = _Store(), {"bad": _room(goal_state={"hard_close": True})}
    _cycle(store, rooms, 0)
    assert [m for m in range(1, 61) if _cycle(store, rooms, m)["reminder"]] == [10, 20, 30, 40, 50, 60]


def test_night_reminders_do_not_use_up_the_limit():
    store, rooms = _Store(), {"bad": _room()}
    _cycle(store, rooms, 0)
    night = [m for m in range(1, 61) if _cycle(store, rooms, m, quiet=True)["reminder"]]
    assert night == [20, 40, 60] and store.room("bad")[REMINDERS_SENT] == 0
    morning = [m for m in range(61, 200) if _cycle(store, rooms, m)["reminder"]]
    assert morning == [80, 100]


def test_automatic_measures_are_not_reminded():
    store = _Store()
    fan = _room(configured_actuators={"exhaust_fan": "switch.f", "mechanical_exhaust_active": True, "window_open": False},
                fan_automation={"state": "stopping", "label_key": "stopping"})
    rooms = {"bad": fan}
    from custom_components.freshairiq.notification_policy import _automatic  # noqa: PLC0415
    assert _automatic("Close", fan)                       # FreshAirIQ switches the fan off itself
    _cycle(store, rooms, 0)
    assert not any(_cycle(store, rooms, m)["reminder"] for m in range(1, 121))


def test_summarised_reminder_for_several_rooms():
    store = _Store()
    rooms = {"bad": _room("bad"), "kueche": _room("kueche"), "flur": _room("flur", followed=16)}
    _cycle(store, rooms, 0)
    events = _cycle(store, rooms, 20)
    assert sorted(r["key"] for r in events["reminder"]) == ["bad", "flur", "kueche"]
    messages = [m for m in room_messages(events, store, OPTIONS, True, sensor_recovery=False) if m["reminder"]]
    summary = [m for m in messages if m.get("summarized_room_keys")]
    assert len(messages) == 2 and len(summary) == 1
    assert summary[0]["summarized_room_keys"] == ["bad", "kueche"] and "Bad, Kueche" in summary[0]["title"]
    assert summary[0]["message"].startswith("Erinnerung: ")


# --------------------------------------------------------------------------------------------------- evidence

def test_presence_away_episodes_are_no_evidence():
    data = {"rooms": {"bad": {}}}
    ensure_behaviour_defaults(data["rooms"]["bad"])
    for day in range(15):
        start = T0 + timedelta(days=day)
        sync_active_recommendation(data, {"kind": "ventilate", "room_keys": ["bad"]}, start, {"away": True})
        sync_active_recommendation(data, {"kind": "okay", "room_keys": []}, start + timedelta(minutes=30))
    room = data["rooms"]["bad"]
    assert room["recommendation_actionable"] == 0 and room["recommendation_unactionable"] == 15
    adapt = notification_adaptation(_room(actionable=room["recommendation_actionable"], followed=0), OPTIONS, 10.0)
    assert not adapt["active"] and adapt["reason"] == REASON_FEW_SAMPLES
