"""R07 (0.26.7.2): plan, live and close times are consistent.

Initial estimate, remaining time, total session, forecast horizon and close reason are separate values. Past the target
time with air that still helps there is no "0 min" countdown ("wird neu bewertet"), a negative remaining time at a
close is the intended overrun, the time alone never closes, and a room opened later keeps its own clock and minimum.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.close_wording import close_cause
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.live_coach import r07_time_fields
from custom_components.freshairiq.decision_brain import build_unified_decision
from custom_components.freshairiq.live_coach import align_live_coach_state, refine_live_recommendation
from custom_components.freshairiq.localize import Translator

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 5, "max_duration_min": 20}


def _room(key, elapsed, *, delta=1.2, next5=60.0, ready=True, **extra):
    room = {"key": key, "name": key.title(), "floor": "eg", "calculation_enabled": True, "data_quality": "ok", "active": True,
            "opening_state": "open", "session_elapsed_min": elapsed, "close_decision_ready": ready, "volume_m3": 12.0,
            "moisture_effect_next_5_min_ml": next5, "forecast_5_min_net_moisture_change_ml": next5, "delta_g_m3": delta,
            "close_recommended": False, "action": "Continue ventilating", "goal_state": {"hard_close": False, "goals": []},
            "session_recommended_duration_min": 8.0}
    room.update(extra)
    return room


REC = {"kind": "continue", "status": "keep_ventilating", "room_keys": ["bad"], "duration_min": 8.0, "title": "Weiterlüften"}


# ------------------------------------------------------------------------------------------------ live coach

def test_countdown_while_the_target_lies_ahead():
    out = refine_live_recommendation({"bad": _room("bad", 3.0)}, OPTIONS, dict(REC))
    assert out["kind"] == "continue" and out["live_coach_time_state"] == "countdown"
    assert out["live_coach_remaining_min"] > 0 and out["duration_min"] == out["live_coach_remaining_min"]


@pytest.mark.parametrize("elapsed", [8.0, 12.0, 20.0, 45.0])
def test_past_the_target_with_drying_air_is_reassessed_not_zero_and_never_closed_by_time(elapsed):
    out = refine_live_recommendation({"bad": _room("bad", elapsed, delta=1.5, next5=80.0)}, OPTIONS, dict(REC))
    assert out["kind"] == "continue"                                       # the time alone never closes (F11)
    assert out["live_coach_time_state"] == "reassessing"
    assert out["live_coach_remaining_min"] is None and out["duration_min"] is None
    assert "noch ca." not in out["instruction"]


def test_air_no_longer_helping_closes_and_names_the_physical_reason():
    out = refine_live_recommendation({"bad": _room("bad", 12.0, delta=0.2, next5=2.0)}, OPTIONS, dict(REC))
    assert out["kind"] == "close" and out["live_coach_remaining_min"] == 0.0


def test_room_opened_later_keeps_its_own_minimum_time():
    # the first window is long past its target and the air no longer helps; the second room opened 2 of 5 minutes ago
    rooms = {"bad": _room("bad", 15.0, delta=0.2, next5=2.0), "kueche": _room("kueche", 2.0, delta=0.2, next5=2.0)}
    out = refine_live_recommendation(rooms, OPTIONS, {**REC, "room_keys": ["bad", "kueche"]})
    assert out["kind"] == "continue"


@pytest.mark.parametrize("kind,text", [
    ("temperature_limit", "Deine Temperaturgrenze beim Lüften ist erreicht"),
    ("goals_reached", "Die Ziele des Raums sind erreicht"),
    ("goals_held", "Die Ziele des Raums wurden in dieser Lüftung erreicht"),
])
def test_close_reason_follows_the_rooms_close_kind(kind, text):
    rooms = {"bad": _room("bad", 12.0, close_recommended=True, close_kind=kind, action="Close")}
    out = refine_live_recommendation(rooms, OPTIONS, {**REC, "kind": "close"})
    assert out["live_coach_reason"].startswith(text)
    assert Translator().text(out["live_coach_reason"]) != out["live_coach_reason"]


def test_physical_close_keeps_its_wording_and_unknown_kinds_add_nothing():
    rooms = {"bad": _room("bad", 12.0, close_recommended=True, close_kind="air_no_longer_helps", action="Close")}
    assert refine_live_recommendation(rooms, OPTIONS, {**REC, "kind": "close"})["live_coach_reason"] == "Physikalisches Schließkriterium erreicht"
    assert close_cause([{"close_recommended": True, "close_kind": "temperature_limit"}, {"close_recommended": True, "close_kind": "goals_reached"}])[0] == "temperature_limit"
    assert close_cause([{"close_recommended": False, "close_kind": "temperature_limit"}]) == (None, None)
    assert close_cause(None) == (None, None)


def test_an_aggregate_turning_close_into_continue_leaves_no_countdown():
    rec = {"kind": "continue", "live_coach": True, "live_coach_state": "close", "live_coach_remaining_min": 0.0, "duration_min": 0.0, "summary": "x"}
    align_live_coach_state(rec)
    assert rec["live_coach_remaining_min"] is None and rec["duration_min"] is None


# ------------------------------------------------------------------------------------------------ house time fields

def _fields(kind, remaining, *, active=True, rooms=None):
    rec = {"kind": kind, "room_keys": list((rooms or {}).keys()), "live_coach_baseline_target_min": 8.0}
    return r07_time_fields(rec, rooms or {}, active=active, remaining=remaining, displayed_recommended=10.0, max_elapsed=13.26)


def test_house_time_states_are_separate_and_honest():
    assert _fields("okay", 10.0, active=False) == {"remaining_duration_state": "plan", "initial_duration_estimate_min": 10.0,
                                                   "session_total_min": None, "close_reason_kind": None,
                                                   "remaining_duration_reason": None}
    assert _fields("continue", 4.0)["remaining_duration_state"] == "countdown"
    reassess = _fields("continue", None)
    assert reassess["remaining_duration_state"] == "reassessing" and reassess["initial_duration_estimate_min"] == 8.0
    assert reassess["session_total_min"] == 13.3
    assert _fields("close", 0.0)["remaining_duration_state"] == "close"
    assert _fields("close", -5.3)["remaining_duration_state"] == "overrun"          # the intended overrun, shown clearly


def test_house_close_reason_kind_comes_from_the_closed_rooms():
    rooms = {"bad": {"key": "bad", "close_recommended": True, "close_kind": "temperature_limit"},
             "flur": {"key": "flur", "close_recommended": True, "close_kind": "air_no_longer_helps"}}
    assert _fields("close", 0.0, rooms=rooms)["close_reason_kind"] == "temperature_limit"
    assert _fields("close", 0.0, rooms={"flur": rooms["flur"]})["close_reason_kind"] is None
    assert _fields("continue", None, rooms=rooms)["close_reason_kind"] is None


# ------------------------------------------------------------------------------------------------ explanation

def test_decision_brain_shows_reassessing_instead_of_a_countdown():
    rooms = {"bad": _room("bad", 12.0)}
    rec = {"kind": "continue", "room_keys": ["bad"], "live_coach_target_min": 8.0, "live_coach_remaining_min": None,
           "live_coach_time_state": "reassessing"}
    brain = build_unified_decision(rec, rooms, OPTIONS)["decision_brain"]
    # the planned target is over: no outdated "Ziel etwa 8 min", the reason why no remaining time can be given
    assert brain["action_line"] == "Restzeit nicht bestimmbar – FreshAirIQ bewertet jeden Zyklus neu"
    assert Translator().text(brain["action_line"]) == "Remaining time cannot be determined – FreshAirIQ reassesses every cycle"
    rec["live_coach_time_reason"] = "Restzeit nicht bestimmbar – eine Feuchtequelle ist noch aktiv"
    assert build_unified_decision(rec, rooms, OPTIONS)["decision_brain"]["action_line"] == rec["live_coach_time_reason"]
