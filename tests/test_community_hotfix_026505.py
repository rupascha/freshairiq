"""0.26.5.5 community hotfix (pure parts): fan follow-up held by a valid recommendation after a moisture
source (Simon42 #167/#170/#181) and the house "open after close" push guard (GitHub #15).

The full chains run in ha_tests/test_community_hotfix_026505.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.actuator_control import FAN_CONTROL_MOISTURE_SOURCE, decide_fan
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.notification_policy import house_reopen_held
from custom_components.freshairiq.const import DEFAULT_OPTIONS

NOW = datetime(2026, 10, 30, 7, 0, tzinfo=timezone.utc)


def _source(mem, minutes, *, hold):
    return decide_fan(mode=FAN_CONTROL_MOISTURE_SOURCE, fan_on=True, demand=False, now=NOW + timedelta(minutes=minutes),
                      follow_up_min=10, max_runtime_min=60, mem=mem, source_hold=hold)


def test_a_valid_recommendation_after_the_source_holds_the_follow_up() -> None:
    mem = {"owned": True, "since": NOW.isoformat(), "last_demand": NOW.isoformat(), "command": "on", "command_state": "confirmed"}
    assert _source(mem, 12, hold=True) is None and mem["reason"] == "follow_up"
    assert _source(mem, 13, hold=False) == "off" and mem["reason"] == "follow_up_ended"


def test_the_maximum_runtime_still_stops_a_held_fan() -> None:
    mem = {"owned": True, "since": NOW.isoformat(), "last_demand": NOW.isoformat(), "command": "on", "command_state": "confirmed"}
    assert _source(mem, 61, hold=True) == "off" and mem["reason"] == "max_runtime"


def test_after_the_shower_the_fan_room_keeps_its_continue_while_the_air_is_drier() -> None:
    def fan_room(ended):
        return RoomInput("bad", "Bad", 22.0, 75.0, 21.0, 55.0, 9.4, True, 900, session_active=True, session_elapsed_min=25.0,
                         session_start_temp=22.0, learning_rate=0.03, session_fresh_measurements=3, mechanical_only=True,
                         moisture_source_recovery=True, moisture_source_ended_min=ended)
    assert evaluate_room(fan_room(12.0), DEFAULT_OPTIONS, False).action == "Continue ventilating"


ROOMS = {"bad": {"surface_rh": 70}}


def test_house_open_push_waits_after_a_close_push() -> None:
    options = {"repeat_recommendation_cooldown_min": 120}
    closed = NOW.isoformat()
    iq = {"room_keys": ["bad"]}
    assert house_reopen_held("ventilate", closed, NOW + timedelta(minutes=35), options, iq, ROOMS)
    assert not house_reopen_held("ventilate", closed, NOW + timedelta(minutes=121), options, iq, ROOMS)
    assert not house_reopen_held("ventilate", None, NOW, options, iq, ROOMS)
    assert not house_reopen_held("close", closed, NOW + timedelta(minutes=35), options, iq, ROOMS)
    # protection is never held back; unknown rooms do not count
    assert not house_reopen_held("ventilate", closed, NOW + timedelta(minutes=35), options, iq, {"bad": {"surface_rh": 92}})
    assert house_reopen_held("ventilate", closed, NOW + timedelta(minutes=35), options, {"room_keys": ["x"]}, ROOMS)
