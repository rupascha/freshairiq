from pathlib import Path

from custom_components.freshairiq.measurement_frame import session_measurement_quality


ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def test_strict_gate_requires_activity_from_both_climate_channels():
    only_temperature = session_measurement_quality(
        2, temperature_reports=2, humidity_reports=0
    )
    assert only_temperature["quality"] == "limited"
    assert only_temperature["eligible"] is False
    assert only_temperature["timestamp_gate_passed"] is False
    assert only_temperature["learning_weight"] == 0.0

    only_humidity = session_measurement_quality(
        2, temperature_reports=0, humidity_reports=2
    )
    assert only_humidity["quality"] == "limited"
    assert only_humidity["eligible"] is False
    assert only_humidity["timestamp_gate_passed"] is False

    both = session_measurement_quality(
        2, temperature_reports=1, humidity_reports=1
    )
    assert both["quality"] == "good"
    assert both["eligible"] is True
    assert both["timestamp_gate_passed"] is True
    assert both["learning_weight"] == 0.75


def test_post_close_refresh_cannot_retroactively_satisfy_timestamp_gate():
    quality = session_measurement_quality(
        0,
        temperature_reports=0,
        humidity_reports=0,
        final_temperature_feedback=True,
        final_humidity_feedback=True,
    )
    assert quality["eligible"] is False
    assert quality["timestamp_gate_passed"] is False
    assert quality["learning_weight"] == 0.0


def test_final_feedback_upgrades_only_an_already_eligible_session():
    quality = session_measurement_quality(
        2,
        temperature_reports=1,
        humidity_reports=1,
        final_temperature_feedback=True,
        final_humidity_feedback=True,
    )
    assert quality["quality"] == "high"
    assert quality["eligible"] is True
    assert quality["learning_weight"] == 1.0


def test_coordinator_persists_and_audits_opening_report_timestamps():
    assert 'mem["session_open_temperature_reported_at"] = temp_reported' in COORDINATOR
    assert 'mem["session_open_humidity_reported_at"] = humidity_reported' in COORDINATOR
    assert 'report_at > report_window_start' in COORDINATOR
    assert 'report_at <= report_window_end' in COORDINATOR
    assert '"session_open_temperature_reported_at": mem.get("session_open_temperature_reported_at")' in COORDINATOR
    assert '"session_open_humidity_reported_at": mem.get("session_open_humidity_reported_at")' in COORDINATOR


def test_legacy_frame_quality_cannot_bypass_strict_timestamp_learning_gate():
    assert 'session_activity_eligible = bool(session_quality.get("timestamp_gate_passed"))' in COORDINATOR
    assert 'start_learning_valid = session_activity_eligible' in COORDINATOR
    assert 'end_learning_valid = session_activity_eligible' in COORDINATOR
    assert 'mem["session_prediction_learning_weight"] = activity_weight if session_activity_eligible else 0.0' in COORDINATOR


def test_good_quality_weight_cannot_be_promoted_by_old_frame_class():
    assert 'frame_weight = activity_weight' in COORDINATOR
    assert 'max({"excellent": 1.0, "acceptable": 0.75, "held": 0.35}' not in COORDINATOR

class _BadInt:
    def __int__(self):
        raise ValueError("bad int")


def test_split_counter_parser_fails_closed_for_bad_runtime_values():
    quality = session_measurement_quality(
        2,
        temperature_reports=_BadInt(),
        humidity_reports=_BadInt(),
    )
    assert quality["eligible"] is False
    assert quality["temperature_reports"] == 0
    assert quality["humidity_reports"] == 0
