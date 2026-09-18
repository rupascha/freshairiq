"""Behaviour/session intelligence coverage with immutable physical semantics."""
from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.freshairiq.intelligence import (
    build_intelligence_state,
    clear_session_behaviour,
    learn_completed_session,
    learn_outcome_feedback,
    mark_recommendation_followed,
    sync_active_recommendation,
)


def _recommendation(**overrides):
    base = {
        "kind": "ventilate", "room_keys": ["living"], "duration_min": 10,
        "estimated_removed_ml": 100, "expected_temperature_change_c": -0.5,
        "estimated_reheat_cost": 0.04, "forecast_confidence": 80,
        "selected_option_id": "now", "title": "Lüften", "summary": "Jetzt lüften",
        "instruction": "Fenster öffnen", "reasons": ["Außenluft trockener"],
    }
    base.update(overrides)
    return base


def test_active_recommendation_episode_follow_and_finalize():
    store = {"rooms": {"living": {}}}
    now = datetime(2026, 9, 14, 8, 0)
    rec = _recommendation()
    assert sync_active_recommendation(store, rec, now) is True
    room = store["rooms"]["living"]
    assert mark_recommendation_followed(store, room, "living", now + timedelta(minutes=4)) is True
    assert room["session_predicted_removed_ml"] == 100
    assert room["avg_follow_delay_min"] == 4.0

    # Repeated refresh stays in the same episode and may update forecast values.
    updated = _recommendation(duration_min=12, estimated_removed_ml=130)
    assert sync_active_recommendation(store, updated, now + timedelta(minutes=5)) is False
    assert store["iq_active_advice"]["duration_min"] == 12

    # Ending/changing the episode finalises behavioural evidence exactly once.
    assert sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, now + timedelta(minutes=6)) is True
    assert room["recommendation_opportunities"] == 1
    assert room["recommendation_followed"] == 1
    assert room["routine_response_samples"] == 1
    assert room["strategy_samples"] == 1


def test_follow_rejects_wrong_room_stale_and_invalid_advice():
    room = {}
    now = datetime(2026, 9, 14, 10, 0)
    assert not mark_recommendation_followed({}, room, "x", now)
    store = {"iq_active_advice": {"room_keys": ["a"], "issued_at": (now - timedelta(hours=3)).isoformat()}}
    assert not mark_recommendation_followed(store, room, "a", now)
    store["iq_active_advice"]["issued_at"] = "broken"
    assert not mark_recommendation_followed(store, room, "a", now)


def test_completed_session_learns_duration_and_deviation_with_clamp():
    room = {"session_recommended_duration_min": 10}
    learn_completed_session(room, 999)
    assert room["preferred_duration_min"] == 240.0
    assert room["avg_duration_deviation_min"] == 230.0
    learn_completed_session(room, 12)
    assert room["duration_samples"] == 2
    assert room["preferred_duration_min"] < 240.0


def _feedback_room(predicted=100.0, predicted_temp=-0.5):
    return {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": predicted,
        "session_predicted_temperature_change_c": predicted_temp,
        "session_selected_option_id": "now",
        "session_recommended_duration_min": 10,
    }


def test_outcome_feedback_rejects_untrustworthy_samples():
    assert not learn_outcome_feedback({}, 100, -0.5)
    room = _feedback_room(predicted=10)
    assert not learn_outcome_feedback(room, 10, -0.1)
    room = _feedback_room()
    room["session_prediction_snapshot_valid"] = False
    assert not learn_outcome_feedback(room, 100, -0.5)


def test_outcome_feedback_guards_first_extreme_outlier_then_records_evidence():
    room = _feedback_room(predicted=200)
    assert learn_outcome_feedback(room, 20, -0.1)
    assert room["last_outcome_feedback_action"] == "guarded_observation"
    assert room["last_outcome_feedback_applied"] is False
    assert room["outcome_feedback_samples"] == 1
    assert room["outcome_guarded_streak"] == 1
    assert room["outcome_avg_removed_error_ml"] == -180.0

    assert learn_outcome_feedback(room, 22, -0.1)
    assert room["outcome_guarded_streak"] == 2
    assert room["last_outcome_feedback_action"] in {"cautious_confirmation", "shadow_promoted"}


def test_outcome_feedback_normal_sample_updates_temperature_calibration():
    room = _feedback_room(predicted=100, predicted_temp=-1.0)
    assert learn_outcome_feedback(room, 95, -0.8)
    assert room["outcome_feedback_samples"] == 1
    assert room["outcome_success_rate"] == 100.0
    assert room["outcome_temperature_factor"] != 1.0
    assert room["last_outcome_feedback_applied"] is True


def test_clear_session_behaviour_resets_prediction_contract():
    room = _feedback_room()
    room.update({"session_prediction_snapshot_pending": True, "session_prediction_reference": "x"})
    clear_session_behaviour(room)
    assert room["session_recommendation_followed"] is False
    assert room["session_predicted_removed_ml"] is None
    assert room["session_prediction_snapshot_valid"] is False
    assert room["session_prediction_snapshot_pending"] is False
    assert room["session_selected_option_id"] is None


def test_intelligence_state_exposes_confidence_and_activity_without_mutating_decision():
    room = {
        "calculation_enabled": True, "data_quality": "ok", "learning_samples": 20,
        "behaviour_duration_samples": 20, "outcome_feedback_samples": 4,
        "routine_source_buckets": {}, "strategy_buckets": {},
    }
    rec = _recommendation(future_weather_used=True, consolidation_checks=["ok"])
    state = build_intelligence_state({"living": room}, rec, forecast_confidence=80, overnight_confidence=70, presence_confidence=100, night_samples=12, now=datetime(2026,9,14))
    assert 15 <= state["confidence"] <= 98
    assert state["decision"]["selected_option_id"] == "now"
    assert "Wetterentwicklung simuliert" in state["activities"] or "Entscheidung konsolidiert" in state["activities"]
