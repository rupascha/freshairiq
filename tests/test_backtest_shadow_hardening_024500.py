"""Finite-number and corrupt-persistence hardening for v0.25.0.7."""
from __future__ import annotations

import json

from custom_components.freshairiq.forecast_backtest import backtest_summary
from custom_components.freshairiq.shadow_learning import ensure_shadow_defaults, process_shadow_feedback


def _record(*rooms):
    return {
        "valid": True,
        "model_version": "0.25.0.7",
        "started_at": "2026-09-14T08:00:00+02:00",
        "ended_at": "2026-09-14T08:10:00+02:00",
        "room_results": list(rooms),
    }


def test_backtest_rejects_nan_and_inf_without_polluting_metrics():
    rooms = [
        {
            "key": "good", "name": "Good", "comparable": True,
            "predicted_removed_ml": 100, "actual_removed_ml": 110,
            "moisture_error_ml": 10, "forecast_confidence": 80,
            "forecast_horizon_min": 10, "direction_correct": True,
        },
        {
            "key": "bad", "name": "Bad", "comparable": True,
            "predicted_removed_ml": float("nan"), "actual_removed_ml": float("inf"),
            "moisture_error_ml": float("nan"), "forecast_confidence": float("inf"),
            "forecast_horizon_min": float("nan"), "direction_correct": None,
            "temperature_error_c": float("nan"), "close_time_error_min": float("inf"),
            "cost_error": float("-inf"),
        },
    ]
    result = backtest_summary([_record(*rooms)])
    json.dumps(result, allow_nan=False)
    assert result["overall"]["moisture_mae_ml"] == 10.0
    bad = next(room for room in result["rooms"] if room["key"] == "bad")
    assert bad["moisture_mae_ml"] is None
    assert bad["magnitude_accuracy_percent"] is None


def test_backtest_ignores_nonfinite_timeline_points():
    room = {
        "key": "living", "name": "Living", "comparable": True,
        "predicted_removed_ml": 100, "actual_removed_ml": 110,
        "moisture_error_ml": 10, "forecast_confidence": 80,
        "forecast_horizon_min": 10, "direction_correct": True,
        "forecast_timeline": [
            {"checkpoint_min": 5, "predicted_final_removed_ml": float("nan")},
            {"checkpoint_min": 10, "predicted_final_removed_ml": 108},
        ],
    }
    replay = backtest_summary([_record(room)])["timeline_replay"]
    assert len(replay) == 1
    assert replay[0]["checkpoint"] == "+10"


def _corrupt_room():
    room = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": "nan"}
    ensure_shadow_defaults(room)
    room.update({
        "shadow_learning_generation": "broken",
        "shadow_learning_samples": "nan",
        "shadow_learning_total_samples": float("inf"),
        "shadow_learning_cooldown": "bad",
        "shadow_learning_promotions": "bad",
        "shadow_learning_rollbacks": "bad",
        "shadow_learning_candidates": {
            "1.000": {"samples": "bad", "abs_error": float("nan"), "sq_error": float("inf"), "wins": "bad"}
        },
    })
    return room


def test_shadow_learning_repairs_corrupt_counters_instead_of_crashing():
    room = _corrupt_room()
    result = process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    assert result["action"] == "observing"
    assert room["shadow_learning_samples"] == 1
    assert room["shadow_learning_total_samples"] == 1
    assert room["shadow_learning_candidates"]["1.000"]["samples"] == 1


def test_shadow_rollback_corrupt_accumulators_are_repaired():
    room = _corrupt_room()
    room.update({
        "shadow_rollback_active": True,
        "shadow_rollback_previous_factor": 1.0,
        "shadow_rollback_promoted_factor": 1.08,
        "shadow_rollback_samples": "nan",
        "shadow_rollback_active_error": float("nan"),
        "shadow_rollback_previous_error": "bad",
        "shadow_rollback_previous_wins": float("inf"),
    })
    result = process_shadow_feedback(room, predicted_removed_ml=108, actual_removed_ml=100)
    assert result["action"] == "guarding_promotion"
    assert result["samples"] == 1
    assert room["shadow_rollback_active_error"] == 8.0
    assert room["shadow_rollback_previous_error"] == 0.0


def test_shadow_replaces_corrupt_candidate_rows_and_ignores_unknown_candidate_keys():
    room = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": 20}
    ensure_shadow_defaults(room)
    room["shadow_learning_candidates"] = {
        "1.000": "broken",
        "not-a-multiplier": {"samples": 999, "abs_error": -999999, "wins": 999},
    }
    result = None
    for _ in range(8):
        result = process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=115)
    assert result is not None
    assert result["action"] in {"promoted", "no_promotion", "baseline_good"}
    assert isinstance(room["shadow_learning_candidates"], dict)


def test_shadow_invalid_rollback_factors_disable_guard_and_continue_safely():
    room = {"outcome_removed_factor": 1.0, "outcome_feedback_samples": 20}
    ensure_shadow_defaults(room)
    room.update({
        "shadow_rollback_active": True,
        "shadow_rollback_previous_factor": "bad",
        "shadow_rollback_promoted_factor": 0,
    })
    result = process_shadow_feedback(room, predicted_removed_ml=100, actual_removed_ml=105)
    assert room["shadow_rollback_active"] is False
    assert result["action"] == "observing"
