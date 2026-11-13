"""0.26.5.5 (F06, GitHub #24): the live coach only counts rooms that are really aired right now.

Bathroom window open 1.3 min (minimum time 5 min, close not released), dining room already
closed but still ``active`` while its final measurement runs: the coach took the dining
room's 5.3 min as the airing time and turned "continue" into "close" for the bathroom.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.opening_strategy import synchronize_room_presentation_actions

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 5, "max_duration_min": 30}


def _room(key, elapsed, *, state="open", next5=11.0, ready=True, pending=False, released=False, fan=False, delta=1.2, floor="eg"):
    return {"key": key, "name": key.title(), "floor": floor, "calculation_enabled": True, "data_quality": "ok", "active": True,
            "opening_state": state, "session_elapsed_min": elapsed, "session_target_min": 5.0, "close_decision_ready": ready,
            "session_finalization_pending": pending, "moisture_effect_next_5_min_ml": next5, "volume_m3": 12.0,
            "delta_g_m3": delta, "close_recommended": released, "action": "Close" if released else "Continue ventilating",
            "goal_state": {"hard_close": released, "goals": []},
            "configured_actuators": {"mechanical_exhaust_active": fan, "exhaust_fan": "switch.f" if fan else None}}


REC = {"kind": "continue", "status": "keep_ventilating", "room_keys": ["bad"], "duration_min": 3.7, "title": "Weiterlüften"}


def test_github_24_a_closed_room_in_its_final_measurement_does_not_time_the_new_window() -> None:
    rooms = {"bad": _room("bad", 1.3), "esszimmer": _room("esszimmer", 5.3, state="closed", next5=3.0)}
    out = refine_live_recommendation(rooms, OPTIONS, dict(REC))
    assert out["kind"] == "continue" and out["room_keys"] == ["bad"]
    assert out["live_coach_remaining_min"] == pytest.approx(3.7, abs=0.05)
    # the same as with only the really open bathroom
    alone = refine_live_recommendation({"bad": _room("bad", 1.3)}, OPTIONS, dict(REC))
    assert (alone["kind"], alone["live_coach_state"]) == (out["kind"], out["live_coach_state"])


@pytest.mark.parametrize("old", [
    {"state": "closed"},                      # closed, final measurement flag not set yet
    {"state": "closed", "pending": True},     # closed, final measurement running
    {"state": "open", "pending": True},       # flag set, raw state lagging
])
@pytest.mark.parametrize("young", [40 / 60, 80 / 60])
def test_variants_of_the_closed_older_room(old, young) -> None:
    rooms = {"bad": _room("bad", young), "esszimmer": _room("esszimmer", 5.6, next5=2.0, **old)}
    assert refine_live_recommendation(rooms, OPTIONS, dict(REC))["kind"] == "continue"


def test_two_really_open_windows_wait_for_the_younger_one() -> None:
    rooms = {"bad": _room("bad", 1.3, next5=4.0), "schlaf": _room("schlaf", 7.0, next5=3.0, floor="og")}
    rec = {**REC, "room_keys": ["bad", "schlaf"]}
    assert refine_live_recommendation(rooms, OPTIONS, dict(rec))["kind"] == "continue"
    rooms["bad"]["session_elapsed_min"] = 6.0
    # Testvermerk 0.26.7.0 (F11): with 1.2 g/m³ drier air both keep going after their minimum time; once the air no
    # longer dries (difference at most close_delta) the close comes as before – both had their minimum time.
    assert refine_live_recommendation(rooms, OPTIONS, dict(rec))["kind"] == "continue"
    for room in rooms.values():
        room["delta_g_m3"] = 0.3
    assert refine_live_recommendation(rooms, OPTIONS, dict(rec))["kind"] == "close"
    rooms["bad"]["session_elapsed_min"] = 1.3
    assert refine_live_recommendation(rooms, OPTIONS, dict(rec))["kind"] == "continue"  # still waits for the younger one


def test_protection_still_closes_at_once_with_its_own_reason() -> None:
    # the young room's own released close (e.g. moisture coming in) is protection
    rooms = {"bad": _room("bad", 1.3, released=True, delta=-0.5), "esszimmer": _room("esszimmer", 5.3, state="closed")}
    out = refine_live_recommendation(rooms, OPTIONS, dict(REC))
    assert out["kind"] == "close" and out["live_coach_state"] == "protection_close"


def test_an_exhaust_fan_room_without_open_window_is_still_aired() -> None:
    rooms = {"wk": _room("wk", 12.0, state="closed", fan=True, next5=30.0)}
    out = refine_live_recommendation(rooms, OPTIONS, {**REC, "room_keys": ["wk"]})
    assert out.get("live_coach") is True  # the coach still evaluates the fan airing


def test_presentation_never_closes_a_room_before_its_own_minimum_time() -> None:
    """Invariant: a non-urgent house close never writes action=Close for a room with close_recommended off
    before its own minimum time (single window, staggered windows, final measurement, fans)."""
    rooms = {"bad": _room("bad", 1.3), "schlaf": _room("schlaf", 6.0, released=True)}
    rec = {"kind": "close", "room_keys": ["bad", "schlaf"]}
    synchronize_room_presentation_actions(rec, rooms, min_duration_min=5)
    assert rooms["schlaf"]["action"] == "Close"
    assert rooms["bad"]["action"] == "Continue ventilating" and rooms["bad"]["close_recommended"] is False
    # protection: moisture coming into the young room closes it
    rooms = {"bad": _room("bad", 1.3, delta=-0.4)}
    synchronize_room_presentation_actions({"kind": "close", "room_keys": ["bad"]}, rooms, min_duration_min=5)
    assert rooms["bad"]["action"] == "Close"
    # past its own minimum time the house close applies as before
    rooms = {"bad": _room("bad", 5.5)}
    synchronize_room_presentation_actions({"kind": "close", "room_keys": ["bad"]}, rooms, min_duration_min=5)
    assert rooms["bad"]["action"] == "Close"


def test_presentation_with_unknown_or_broken_age_keeps_the_house_close() -> None:
    for elapsed in (None, "x"):
        rooms = {"bad": {**_room("bad", 1.0), "session_elapsed_min": elapsed}}
        synchronize_room_presentation_actions({"kind": "close", "room_keys": ["bad"]}, rooms, min_duration_min=5)
        assert rooms["bad"]["action"] == "Close"
