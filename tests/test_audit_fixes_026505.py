"""0.26.5.5 audit (30.10.): protection inside the minimum time, F02 follow-up from the end of the moisture
source, F03 a moisture source never hides another room's close.

Each test reproduces the finding with the unchanged code path (room engine, house aggregate,
live coach, presentation, notifications) and the default options.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.notification_policy import effective_room_action
from custom_components.freshairiq.opening_strategy import (
    house_aligned_room_actions,
    keep_moisture_sources_open,
    synchronize_room_presentation_actions,
)

OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "comfort"}


# --- Protection inside the configured minimum time ------------------------------------------
# (The five-minute floor of the first audit fix was withdrawn by the owner on 30.10.: the
# configured minimum applies; the decisions themselves must keep a useful airing open.)

def _window(elapsed, ref_rh=60.0, ref_t=12.0):
    return RoomInput("bad", "Bad", 22.0, 60.0, ref_t, ref_rh, 6.0, True, 600, session_active=True,
                     session_elapsed_min=elapsed, session_start_temp=22.0, learning_rate=0.03, session_fresh_measurements=2)


def test_the_configured_minimum_stays_three_minutes() -> None:
    assert DEFAULT_OPTIONS["min_duration_min"] == 3.0
    assert evaluate_room(_window(2.0), OPTIONS, False).action == "Continue ventilating"


def test_moisture_coming_in_closes_inside_the_minimum() -> None:
    wet = evaluate_room(_window(2.0, ref_rh=70.0, ref_t=21.0), OPTIONS, False)
    assert wet.delta_g_m3 < 0 and wet.action == "Close" and wet.close_recommended


def _coach(key, elapsed, next5=3.0, **extra):
    room = {"key": key, "name": key.title(), "calculation_enabled": True, "data_quality": "ok", "active": True,
            "opening_state": "open", "session_elapsed_min": elapsed, "close_decision_ready": True, "volume_m3": 40.0,
            "forecast_5_min_moisture_effect_ml": next5, "forecast_5_min_temperature_change_c": -0.1, "delta_g_m3": 1.0,
            "configured_actuators": {"mechanical_exhaust_active": False, "window_open": True}}
    room.update(extra)
    return room


def test_live_coach_closes_on_moisture_coming_in_inside_the_minimum() -> None:
    rec = {"kind": "continue", "duration_min": 5.0, "reasons": []}
    assert refine_live_recommendation({"bad": _coach("bad", 2.0)}, OPTIONS, dict(rec))["kind"] == "continue"
    wet = refine_live_recommendation({"bad": _coach("bad", 2.0, next5=-8.0, delta_g_m3=-0.8)}, OPTIONS, dict(rec))
    assert wet["kind"] == "close"


def test_github_24_a_room_in_its_final_measurement_does_not_time_the_new_window() -> None:
    rooms = {"bad": _coach("bad", 1.5, next5=11.0), "ess": _coach("ess", 9.0, opening_state="closed", session_finalization_pending=True)}
    assert refine_live_recommendation(rooms, OPTIONS, {"kind": "continue", "duration_min": 3.0, "room_keys": ["bad"]})["kind"] == "continue"


# --- F02: follow-up from the end of the source ---------------------------------------------

def _source_room(**extra):
    fields = dict(session_active=True, session_elapsed_min=12.0, session_start_temp=21.0, learning_rate=0.03,
                  session_fresh_measurements=2, session_target_min=5.0)
    fields.update(extra)
    return RoomInput("bad", "Bad", 21.0, 60.0, 20.0, 58.0, 40.0, True, 600, **fields)


def test_audit_repro_a_source_that_just_ended_keeps_its_follow_up() -> None:
    active = evaluate_room(_source_room(moisture_source_active=True), OPTIONS, False)
    assert active.action == "Continue ventilating" and not active.close_recommended
    just_ended = evaluate_room(_source_room(moisture_source_recovery=True, moisture_source_ended_min=1.0), OPTIONS, False)
    assert just_ended.delta_g_m3 > 0.9
    assert just_ended.action == "Continue ventilating" and not just_ended.close_recommended


@pytest.mark.parametrize(("ended", "elapsed", "kept"), [
    (7.5, 12.0, True),     # the follow-up of 8 min is not over yet
    (8.5, 12.0, False),    # over
    (2.0, 40.0, True),     # long airing, source ended late
    (None, 12.0, False),   # unknown end: counts from the start of the airing (unchanged)
    (None, 6.0, True),
])
def test_the_follow_up_counts_from_the_end_of_the_source(ended, elapsed, kept) -> None:
    result = evaluate_room(_source_room(moisture_source_recovery=True, moisture_source_ended_min=ended, session_elapsed_min=elapsed), OPTIONS, False)
    # Testvermerk 0.26.7.0 (F11): the reference air here is ~1 g/m³ drier, so the airing continues after the follow-up
    # as well (no close on low return while drying is possible). The follow-up itself stays visible in the reason.
    assert result.action == "Continue ventilating" and not result.close_recommended
    assert result.reason.startswith("Active internal moisture source") is kept


def test_no_follow_up_when_the_reference_air_is_not_drier() -> None:
    wet = _source_room(moisture_source_recovery=True, moisture_source_ended_min=1.0)
    wet = RoomInput("bad", "Bad", 21.0, 60.0, 21.0, 66.0, 40.0, True, 600, **{k: getattr(wet, k) for k in (
        "session_active", "session_elapsed_min", "session_start_temp", "learning_rate", "session_fresh_measurements",
        "session_target_min", "moisture_source_recovery", "moisture_source_ended_min")})
    assert evaluate_room(wet, OPTIONS, False).action == "Close"


# --- F03: a moisture source never hides another room's close -------------------------------

def _room(key, name, floor, **extra):
    room = {"key": key, "name": name, "floor": floor, "volume_m3": 30.0, "active": True, "close_decision_ready": True,
            "data_quality": "ok", "calculation_enabled": True,
            "forecast_5_min_net_moisture_change_ml": 1.0, "forecast_5_min_moisture_effect_ml": 1.0,
            "forecast_5_min_temperature_change_c": -0.1, "session_elapsed_min": 12.0, "goal_state": {"hard_close": False, "goals": []}}
    room.update(extra)
    return room


def _rooms(hard=True):
    bad = _room("bad", "Bad", "ground_floor", action="Continue ventilating", close_recommended=False, delta_g_m3=2.0,
                moisture_source_active=True, moisture_source_label="Dusche", forecast_5_min_moisture_effect_ml=40.0)
    schlaf = _room("schlafzimmer", "Schlafzimmer", "upper_floor", action="Close", close_recommended=True, delta_g_m3=-1.0,
                   forecast_5_min_moisture_effect_ml=-6.0, goal_state={"hard_close": hard, "goals": []})
    return {"bad": bad, "schlafzimmer": schlaf}


def shower_and_bedroom_chain(hard: bool):
    """Room engine results → house decision → presentation → house-aligned room actions."""
    rooms = _rooms(hard)
    initial = {"kind": "close", "status": "close_windows", "room_keys": ["schlafzimmer"], "title": "Jetzt schließen",
               "instruction": "Schlafzimmer schließen", "reasons": []}
    out = stabilise_recommendation(initial, rooms, OPTIONS)
    assert out["kind"] == "close" and out["room_keys"] == ["schlafzimmer"]
    assert out["instruction"] == "Schlafzimmer schließen · Bad offen lassen"
    assert out["moisture_source_kept_open"] == ["bad"]
    # the rest of the chain: presentation, house-aligned room actions, push texts
    keep_moisture_sources_open(out, rooms, OPTIONS)
    synchronize_room_presentation_actions(out, rooms, min_duration_min=OPTIONS["min_duration_min"])
    house_aligned_room_actions(out, rooms)
    assert rooms["schlafzimmer"]["action"] == "Close" and rooms["schlafzimmer"]["house_aligned_action"] == "close"
    assert rooms["bad"]["action"] == "Continue ventilating" and rooms["bad"]["house_aligned_action"] == "continue_ventilating"
    assert effective_room_action(rooms["schlafzimmer"], out, rooms) == "Close"
    assert effective_room_action(rooms["bad"], out, rooms) == "Continue ventilating"
    return out, rooms  # the push text of this result is checked in ha_tests/test_audit_push_026505.py


@pytest.mark.parametrize("hard", [True, False])
def test_audit_repro_the_bedroom_close_stays_beside_the_running_shower(hard) -> None:
    shower_and_bedroom_chain(hard)


def test_only_the_source_room_open_still_keeps_ventilating() -> None:
    rooms = {"bad": _rooms()["bad"]}
    out = stabilise_recommendation({"kind": "close", "room_keys": ["bad"], "instruction": "Bad schließen"}, rooms, OPTIONS)
    assert out["kind"] == "continue" and out["room_keys"] == ["bad"] and out["instruction"] == "Wirksame Lüftung weiterführen"
