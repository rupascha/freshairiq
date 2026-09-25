from datetime import datetime, timedelta
from pathlib import Path

from custom_components.freshairiq.forecast import horizon_forecast
from custom_components.freshairiq.intelligence import learn_outcome_feedback
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def _forecast(horizon: int, recent_rate: float | None, elapsed: float = 63.0, fresh: int = 2):
    return horizon_forecast(
        current_ah=12.0,
        source_ah=6.0,
        current_temp_c=21.0,
        source_temp_c=10.0,
        volume_m3=100.0,
        rate_per_min=0.03,
        airflow_bonus=1.0,
        horizon_min=horizon,
        observation_samples=20,
        running=True,
        session_elapsed_min=elapsed,
        session_fresh_measurements=fresh,
        recent_observed_removed_ml_min=recent_rate,
        target_ah=11.0,
        cap_positive_to_target=True,
    )


def test_running_forecast_uses_recent_measured_stall_instead_of_theoretical_only():
    theoretical = _forecast(30, None)
    stalled = _forecast(30, 0.0)
    assert theoretical["moisture_effect_ml"] == 100  # target limited physical model
    assert stalled["live_adapted"] is True
    assert stalled["live_observation_weight"] >= 0.8
    assert 0 <= stalled["moisture_effect_ml"] < 40
    assert stalled["moisture_effect_ml"] < theoretical["moisture_effect_ml"]


def test_running_forecast_horizon_still_changes_when_measured_rate_is_small():
    f15 = _forecast(15, 0.25)
    f30 = _forecast(30, 0.25)
    f60 = _forecast(60, 0.25)
    assert f15["live_adapted"] and f30["live_adapted"] and f60["live_adapted"]
    assert f15["moisture_effect_ml"] < f30["moisture_effect_ml"] <= f60["moisture_effect_ml"]


def test_early_session_does_not_overreact_to_one_measurement():
    early = _forecast(30, 0.0, elapsed=6.0, fresh=1)
    assert early["live_observation_weight"] < 0.05
    assert early["moisture_effect_ml"] > 80


def test_large_prediction_error_is_held_as_unapplied_evidence_first():
    room = {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 176.0,
        "session_predicted_temperature_change_c": -0.2,
        "outcome_removed_factor": 1.0,
        "outcome_temperature_factor": 1.0,
        "outcome_feedback_samples": 0,
        "outcome_successes": 0,
    }
    assert learn_outcome_feedback(room, 30.0, 0.1) is True
    assert room["last_outcome_feedback_action"] == "guarded_observation"
    assert "unverändert" in room["last_outcome_feedback_reason"]
    assert room["last_outcome_feedback_applied"] is False
    assert room["outcome_removed_factor"] == 1.0
    assert room["last_outcome_feedback_accuracy"] < 40


def test_completed_house_result_carries_learning_feedback_for_dashboard():
    ended = datetime(2026, 9, 11, 15, 20)
    group = {
        "started_at": (ended - timedelta(minutes=60)).isoformat(),
        "sessions": [{
            "event_id": "living:1",
            "key": "living", "name": "Wohnküche", "floor": "EG", "sort_order": 1,
            "volume_m3": 80.0, "removed_ml": 30.0, "duration_min": 60.0,
            "cost": 0.0, "energy_kwh": 0.0, "temp_delta_c": 0.1,
            "predicted_removed_ml": 176.0, "predicted_temperature_change_c": -0.2,
            "prediction_comparable": True,
            "recommendation_followed": True, "learning_valid": True,
            "moisture_source_contaminated": False, "cross_ventilation_minutes": 0.0,
            "outcome_feedback_action": "guarded",
            "outcome_feedback_reason": "Sehr große Abweichung erkannt",
        }],
    }
    result = finalise_ventilation_group(group, ended)
    assert result is not None
    assert result["learning_feedback_action"] == "guarded"
    assert "nur minimal angepasst" in result["learning_feedback_text"]
    assert result["prediction_accuracy_percent"] < 40


def test_details_header_is_separate_from_scroll_body_and_learning_feedback_is_visible():
    assert '<div class="dialog-scroll"><div class="overview">' in JS
    assert '.dialog{width:calc(100vw - 28px)' in JS
    assert 'display:flex;flex-direction:column;overflow:hidden' in JS
    assert '.dialog-scroll{min-height:0;flex:1 1 0;overflow-y:auto' in JS
    assert 'last.learning_feedback_text' in JS
    assert 'result-learning-feedback' in JS


def test_close_state_preserves_negative_over_target_time_for_iq_time_tile():
    assert 'remaining = min(0.0, round(float(displayed_recommended) - max_elapsed, 1))' in COORD
    assert 'remaining > 0 ? `${Math.ceil(remaining)} min` : remaining < 0 ? `+${Math.ceil(Math.abs(remaining))} min` : "0 min"' in JS
