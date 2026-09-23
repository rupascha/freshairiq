import pytest
from custom_components.freshairiq.support_replay import build_sensor_replay_snapshot, replay_sensor_snapshot


def test_real_sensor_failure_shape_reproduces_production_sensor_branch():
    snapshot = build_sensor_replay_snapshot({
        "rooms_ok": 0,
        "issue_quality_counts": {"missing": 1},
        "outdoor_data_quality": "ok",
    })
    result = replay_sensor_snapshot(snapshot)
    assert result == {"kind": "sensor", "status": "sensor_error", "reproduces_sensor_error": True}


def test_mixed_valid_and_bad_rooms_does_not_false_reproduce_house_sensor_error():
    snapshot = build_sensor_replay_snapshot({"rooms_ok": 1, "issue_quality_counts": {"stale": 1}})
    result = replay_sensor_snapshot(snapshot)
    assert result["reproduces_sensor_error"] is False


def test_snapshot_normalises_untrusted_quality_classes_and_counts():
    snapshot = build_sensor_replay_snapshot({"rooms_ok": "0", "issue_quality_counts": {"SECRET ROOM": 2, "missing": "3", "stale": -4}})
    assert snapshot["issue_quality_counts"] == {"missing": 3, "unknown": 2}


def test_empty_snapshot_is_not_created_and_invalid_replay_is_rejected():
    assert build_sensor_replay_snapshot({}) is None
    with pytest.raises(ValueError):
        replay_sensor_snapshot({"schema_version": 999, "target": "build_recommendation"})


def test_snapshot_and_replay_defensively_handle_invalid_numeric_inputs():
    snapshot = build_sensor_replay_snapshot({
        "rooms_ok": object(),
        "issue_quality_counts": {"missing": object()},
    })
    assert snapshot is None
    result = replay_sensor_snapshot({
        "schema_version": 1,
        "target": "build_recommendation",
        "rooms_ok": object(),
        "issue_quality_counts": {"missing": object()},
    })
    assert result["reproduces_sensor_error"] is False


def test_replay_normalises_forbidden_or_ok_issue_bucket_to_unknown():
    result = replay_sensor_snapshot({
        "schema_version": 1,
        "target": "build_recommendation",
        "rooms_ok": 0,
        "issue_quality_counts": {"ok": 1, "private-label": 1},
    })
    assert result["reproduces_sensor_error"] is True
