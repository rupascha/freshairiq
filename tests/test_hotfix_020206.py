from datetime import datetime, timedelta
from pathlib import Path

from custom_components.freshairiq.intelligence import learn_outcome_feedback
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group

ROOT = Path(__file__).resolve().parents[1]


def test_learning_rejects_non_start_snapshot_reference():
    room = {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": False,
        "session_predicted_removed_ml": 120.0,
        "session_predicted_temperature_change_c": -0.3,
    }
    assert learn_outcome_feedback(room, 110.0, -0.2) is False
    assert room["outcome_feedback_samples"] == 0


def test_house_accuracy_uses_only_time_comparable_sessions():
    ended = datetime(2026, 9, 11, 22, 0)
    group = {
        "started_at": (ended - timedelta(minutes=20)).isoformat(),
        "sessions": [
            {
                "event_id": "good", "key": "good", "name": "Gut", "sort_order": 1,
                "volume_m3": 50.0, "removed_ml": 100.0, "duration_min": 5.0,
                "cost": 0.0, "energy_kwh": 0.0, "temp_delta_c": -0.1,
                "predicted_removed_ml": 90.0, "prediction_comparable": True,
                "recommendation_followed": True, "learning_valid": True,
            },
            {
                "event_id": "long", "key": "long", "name": "Zu lang", "sort_order": 2,
                "volume_m3": 50.0, "removed_ml": 300.0, "duration_min": 240.0,
                "cost": 0.0, "energy_kwh": 0.0, "temp_delta_c": -0.2,
                "predicted_removed_ml": 10.0, "prediction_comparable": False,
                "recommendation_followed": True, "learning_valid": True,
            },
        ],
    }
    result = finalise_ventilation_group(group, ended)
    assert result is not None
    assert result["removed_ml"] == 400
    assert result["prediction_actual_removed_ml"] == 100
    assert result["predicted_removed_ml"] == 90
    assert result["prediction_error_ml"] == 10
    assert result["prediction_comparable_rooms"] == 1
    assert result["prediction_accuracy_percent"] == 90


def test_house_five_minute_ui_and_explanation_share_signed_net_source():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'forecast_5_min_net_moisture_change_ml' in coordinator
    assert 'house_next_5_min_moisture_effect_ml' in coordinator
    assert 'houseShortEffect' in card
    assert 'forecastH === 5 && houseShortEffect != null' in card
