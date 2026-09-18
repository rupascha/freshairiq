from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.const import DEFAULT_OPTIONS, MOISTURE_SOURCE_COOKING
from custom_components.freshairiq.intelligence import learn_outcome_feedback
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.moisture_source import update_moisture_source


def _source(mem, now, ah, temp, sources):
    return update_moisture_source(
        mem, now=now, absolute_humidity_g_m3=ah, reference_ah_g_m3=8.0,
        temperature_c=temp, volume_m3=50.0, window_open=False,
        learning_rate_per_min=0.03, airflow_factor=1.0,
        cross_ventilation=False, configured_sources=sources,
    )


def test_cooking_can_be_identified_from_heat_and_moisture_signature():
    mem = {}
    t0 = datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc)
    _source(mem, t0, 10.0, 21.0, [MOISTURE_SOURCE_COOKING, "shower"])
    out = _source(mem, t0 + timedelta(minutes=5), 10.9, 21.7, [MOISTURE_SOURCE_COOKING, "shower"])
    assert out["active"] is True
    assert out["identified_source"] == MOISTURE_SOURCE_COOKING
    assert out["label"] == "Kochen"
    assert "Guten Appetit" in out["message"]


def test_multiple_wet_sources_remain_neutral_when_not_distinguishable():
    mem = {}
    t0 = datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc)
    _source(mem, t0, 10.0, 22.0, ["shower", "bath"])
    out = _source(mem, t0 + timedelta(minutes=5), 10.9, 22.1, ["shower", "bath"])
    assert out["active"] is True
    assert out["identified_source"] is None
    assert out["label"] == "Feuchtequelle"
    assert out["ambiguous"] is True
    assert "nicht eindeutig" in out["message"]


def test_moisture_source_recovery_blocks_early_close():
    opts = dict(DEFAULT_OPTIONS)
    room = RoomInput(
        "bad", "Badezimmer", 22.0, 60.0, 10.0, 55.0, 35.0, True, 400.0,
        session_active=True, session_elapsed_min=5.0, session_start_ah=12.0,
        session_start_temp=22.5, learning_rate=0.03, session_fresh_measurements=2,
        moisture_source_active=False, moisture_source_recovery=True,
    )
    result = evaluate_room(room, opts, False)
    assert result.action == "Continue ventilating"
    assert result.close_recommended is False


def test_repeat_cooldown_default_is_two_hours():
    assert DEFAULT_OPTIONS["repeat_recommendation_cooldown_min"] == 120.0


def test_tiny_absolute_forecast_error_is_not_called_very_large():
    room = {
        "session_recommendation_followed": True,
        "session_prediction_snapshot_valid": True,
        "session_predicted_removed_ml": 30.0,
        "session_predicted_temperature_change_c": -0.2,
    }
    assert learn_outcome_feedback(room, 21.0, -0.2) is True
    assert room["last_outcome_feedback_action"] == "applied"
    assert "Sehr große" not in room["last_outcome_feedback_reason"]
