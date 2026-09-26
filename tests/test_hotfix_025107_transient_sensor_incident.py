
from custom_components.freshairiq.support_incident import build_support_incident, classify_support_code


def trace(kind="sensor", status="sensor_error"):
    return {"final": {"kind": kind, "status": status, "scope": "rooms"}, "invariants": {"selected_rooms_exist": True}}


def test_startup_unknown_rooms_and_missing_outdoor_is_not_high_sensor_incident():
    quality = {
        "rooms_ok": 0,
        "issue_quality_counts": {"unknown": 12},
        "outdoor_data_quality": "missing_or_invalid",
    }
    assert classify_support_code(trace(), quality) is None
    incident = build_support_incident(trace(), quality)
    assert incident["incident"] is False
    assert incident["support_code"] is None
    assert incident["replay_snapshot"] is None


def test_real_missing_room_sensor_still_is_sensor_incident():
    quality = {"rooms_ok": 0, "issue_quality_counts": {"missing": 1}, "outdoor_data_quality": "ok"}
    assert classify_support_code(trace(), quality) == "FAIQ-SENSOR-DATA-001"


def test_stale_sensor_still_is_sensor_incident():
    quality = {"rooms_ok": 2, "stale_rooms": 1, "issue_quality_counts": {"stale": 1}, "outdoor_data_quality": "ok"}
    assert classify_support_code(trace("okay", "ok"), quality) == "FAIQ-SENSOR-DATA-001"


def test_unknown_rooms_with_valid_outdoor_still_is_sensor_incident():
    quality = {"rooms_ok": 0, "issue_quality_counts": {"unknown": 12}, "outdoor_data_quality": "ok"}
    assert classify_support_code(trace(), quality) == "FAIQ-SENSOR-DATA-001"


def test_unknown_plus_real_fault_is_not_suppressed():
    quality = {"rooms_ok": 0, "issue_quality_counts": {"unknown": 11, "invalid": 1}, "outdoor_data_quality": "missing_or_invalid"}
    assert classify_support_code(trace(), quality) == "FAIQ-SENSOR-DATA-001"
