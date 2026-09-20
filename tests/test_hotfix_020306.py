from pathlib import Path

from custom_components.freshairiq.forecast_validation import prediction_duration_comparable
from custom_components.freshairiq.intelligence import learn_outcome_feedback

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def _room():
    return {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 176.0,
        "session_predicted_temperature_change_c": -0.2,
        "outcome_removed_factor": 1.0,
        "outcome_temperature_factor": 1.0,
        "outcome_feedback_samples": 0,
        "outcome_successes": 0,
    }


def test_duration_comparison_is_tight_and_symmetric():
    assert prediction_duration_comparable(20.0, 20.0)
    assert prediction_duration_comparable(18.0, 20.0)
    assert prediction_duration_comparable(22.0, 20.0)
    assert not prediction_duration_comparable(17.9, 20.0)
    assert not prediction_duration_comparable(22.1, 20.0)
    assert prediction_duration_comparable(4.0, 5.0)
    assert prediction_duration_comparable(6.0, 5.0)
    assert not prediction_duration_comparable(3.9, 5.0)


def test_first_extreme_outlier_does_not_change_forecast_factors():
    room = _room()
    assert learn_outcome_feedback(room, 30.0, 0.1) is True
    assert room["last_outcome_feedback_action"] == "guarded_observation"
    assert room["last_outcome_feedback_applied"] is False
    assert room["outcome_removed_factor"] == 1.0
    assert room["outcome_temperature_factor"] == 1.0
    assert room["outcome_guarded_streak"] == 1
    assert room["outcome_avg_removed_error_ml"] == -146.0


def test_repeated_similar_outlier_requires_confirmation_before_learning():
    room = _room()
    learn_outcome_feedback(room, 30.0, 0.1)
    learn_outcome_feedback(room, 32.0, 0.1)
    assert room["last_outcome_feedback_action"] == "cautious_confirmation"
    assert room["last_outcome_feedback_applied"] is True  # temperature feedback may adapt
    assert room["outcome_guarded_streak"] == 2
    # Learning 3.0 keeps the production moisture factor frozen while shadow
    # candidates collect repeated evidence.
    assert room["outcome_removed_factor"] == 1.0
    learn_outcome_feedback(room, 31.0, 0.1)
    assert room["last_outcome_feedback_action"] == "confirmed_outlier"
    assert room["outcome_guarded_streak"] == 3
    assert room["outcome_removed_factor"] == 1.0
    assert room["shadow_learning_samples"] >= 2


def test_opposite_extreme_outlier_resets_confirmation_streak():
    room = _room()
    learn_outcome_feedback(room, 30.0, 0.1)
    room["session_predicted_removed_ml"] = 100.0
    learn_outcome_feedback(room, 300.0, -0.3)
    assert room["outcome_guarded_streak"] == 1
    assert room["outcome_guarded_direction"] == "actual_higher"
    assert room["last_outcome_feedback_applied"] is False


def test_coordinator_separates_physical_runtime_from_measurement_baseline():
    assert 'mem["session_physical_started"] = physical_started.isoformat()' in COORD
    assert 'elapsed_start = mem.get("session_physical_started") or mem.get("session_started")' in COORD
    assert 'elapsed_min=measurement_elapsed' in COORD
    assert 'prediction_duration_comparable(elapsed, snapshot_horizon_f)' in COORD
    assert '"measurement_started_at": measurement_started.isoformat()' in COORD


def test_release_version_020306():
    assert 'VERSION = "0.25.0.42"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.42"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.42"' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert (ROOT / "RELEASE_NOTES_0.20.3.6.md").exists()
