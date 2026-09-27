from custom_components.freshairiq.support_incident import classify_support_code


def _trace():
    return {"final": {"kind": "sensor", "status": "sensor_error", "scope": "rooms"}, "invariants": {}}


def test_startup_filter_rejects_non_numeric_rooms_ok():
    quality = {"rooms_ok": object(), "issue_quality_counts": {"unknown": 3}, "outdoor_data_quality": "missing_or_invalid"}
    assert classify_support_code(_trace(), quality) == "FAIQ-SENSOR-DATA-001"


def test_startup_filter_rejects_non_numeric_unknown_count():
    quality = {"rooms_ok": 0, "issue_quality_counts": {"unknown": object()}, "outdoor_data_quality": "missing_or_invalid"}
    assert classify_support_code(_trace(), quality) == "FAIQ-SENSOR-DATA-001"


def test_startup_filter_rejects_zero_unknown_count():
    quality = {"rooms_ok": 0, "issue_quality_counts": {"unknown": 0}, "outdoor_data_quality": "missing_or_invalid"}
    assert classify_support_code(_trace(), quality) == "FAIQ-SENSOR-DATA-001"
