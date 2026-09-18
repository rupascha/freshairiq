from pathlib import Path

from custom_components.freshairiq.measurement_frame import session_measurement_quality
from custom_components.freshairiq.robustness import sanitize_runtime_session


def test_session_quality_requires_two_real_reports():
    assert session_measurement_quality("not-a-number")["quality"] == "insufficient"
    assert session_measurement_quality(0)["quality"] == "insufficient"
    assert session_measurement_quality(1)["quality"] == "limited"
    good = session_measurement_quality(2)
    assert good["quality"] == "good"
    assert good["eligible"] is True


def test_final_sensor_feedback_upgrades_quality_without_replacing_activity_gate():
    high = session_measurement_quality(2, final_temperature_feedback=True, final_humidity_feedback=True)
    assert high["quality"] == "high"
    assert high["learning_weight"] == 1.0
    still_bad = session_measurement_quality(0, final_temperature_feedback=True, final_humidity_feedback=True)
    assert still_bad["eligible"] is False


def test_hotfix_preserves_close_confirm_and_adds_bounded_final_wait():
    root = Path(__file__).resolve().parents[1]
    const = (root / "custom_components/freshairiq/const.py").read_text()
    coordinator = (root / "custom_components/freshairiq/coordinator.py").read_text()
    card = (root / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert "SESSION_CLOSE_CONFIRM_SECONDS = 3.0" in const
    assert "SESSION_END_MEASUREMENT_WAIT_SECONDS = 10.0" in const
    assert '"homeassistant", "update_entity"' in coordinator
    assert "session_temperature_reports" in coordinator
    assert "session_humidity_reports" in coordinator
    assert "_begin_final_measurement_wait" in coordinator
    assert "feedback_count >= 2 or wait_expired" in coordinator
    assert 'elapsed_end = min(now, datetime.fromisoformat(str(mem.get("session_close_detected_at"))))' in coordinator
    assert "Warte kurz auf die Klimasensoren" in card


def test_new_optional_runtime_flags_are_sanitized_when_present():
    room = {
        "session_active": False,
        "session_prediction_snapshot_valid": False,
        "session_prediction_snapshot_pending": False,
        "session_start_frame_learning_eligible": False,
        "session_moisture_source_detected": False,
        "session_cross_active": False,
        "session_result_base_ml": 0.0,
        "session_result_ml": 0.0,
        "session_cross_seconds": 0.0,
        "session_fresh_measurements": 0,
        "session_forecast_timeline": [],
        "session_close_pending": "false",
    }
    repaired = sanitize_runtime_session(room)
    assert room["session_close_pending"] is False
    assert "session_close_pending" in repaired
