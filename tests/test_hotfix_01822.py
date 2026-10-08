from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.intelligence import learn_outcome_feedback
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.house_strategy import learn_house_outcome


def test_missing_co2_is_not_treated_as_zero_measurement():
    room = RoomInput(
        "living", "Living room", 22, 64, 10, 55, 80, False, 0,
        co2=None,
    )
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    assert result.data_quality == "ok"
    assert result.action in {"Ventilate", "Wait", "Okay", "Do not ventilate"}


def test_valid_high_co2_remains_urgent():
    room = RoomInput(
        "living", "Living room", 22, 50, 10, 50, 80, False, 0,
        co2=float(DEFAULT_OPTIONS["co2_warn"]) + 200,
    )
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    # CO2 remains an urgency input even if humidity itself is normal.
    assert result.data_quality == "ok"
    assert result.action != "Check sensor"


def test_negative_outcome_feedback_is_preserved_as_prediction_error():
    room = {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 100.0,
        "session_predicted_temperature_change_c": -1.0,
    }
    learned = learn_outcome_feedback(room, -50.0, -0.8)
    assert learned is True
    assert room["outcome_avg_removed_error_ml"] == -150.0
    assert room["outcome_success_rate"] == 0.0
    assert room["outcome_removed_factor"] == 1.0
    assert room["last_outcome_feedback_applied"] is False
    assert room["last_outcome_feedback_action"] == "guarded_observation"


def test_house_strategy_keeps_negative_ventilation_outcome():
    store = {}
    events = [{"key": "living", "duration_min": 10, "removed_ml": -120, "cost": 0.1, "predicted_removed_ml": 100}]
    changed = learn_house_outcome(
        store, events, {"living": {"floor": "ground_floor"}},
        cross=False, expected_occupants=2,
    )
    assert changed is True
    assert store["house_strategy_total_removed_ml"] == -120.0
    row = next(iter(store["house_strategy_buckets"].values()))
    assert row["avg_removed_ml"] == -120.0
    assert row["success_rate"] == 0.0
