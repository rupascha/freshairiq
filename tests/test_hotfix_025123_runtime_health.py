from tests.release_version import CURRENT_RELEASE_VERSION
from custom_components.freshairiq.runtime_health import (
    ATTRIBUTE_WARNING_BYTES,
    RECORDER_ATTRIBUTE_LIMIT_BYTES,
    RuntimeHealthMonitor,
    json_payload_bytes,
)
from custom_components.freshairiq.diagnostic_transport import problem_fingerprint


def _payload_over(limit: int) -> dict:
    return {"payload": "x" * (limit + 128)}


def test_json_payload_size_is_utf8_bytes():
    assert json_payload_bytes({"x": "ä"}) == len('{"x":"ä"}'.encode("utf-8"))


def test_protected_large_payload_is_measured_but_not_an_incident():
    monitor = RuntimeHealthMonitor()
    size = monitor.observe_attribute_payload(
        "status", _payload_over(RECORDER_ATTRIBUTE_LIMIT_BYTES), recorder_exposed=False
    )
    snapshot = monitor.snapshot
    assert size > RECORDER_ATTRIBUTE_LIMIT_BYTES
    assert snapshot["incident_count"] == 0
    assert snapshot["active_problem"] is False
    assert snapshot["attribute_payloads"][0]["max_attribute_bytes"] == size
    assert snapshot["attribute_payloads"][0]["recorder_exposed"] is False


def test_recorder_exposed_oversize_payload_becomes_aggregated_incident():
    monitor = RuntimeHealthMonitor()
    payload = _payload_over(RECORDER_ATTRIBUTE_LIMIT_BYTES)
    monitor.observe_attribute_payload("status", payload, recorder_exposed=True, now="2026-09-28T09:00:00+02:00")
    monitor.observe_attribute_payload("status", payload, recorder_exposed=True, now="2026-09-28T09:01:00+02:00")
    incident = monitor.snapshot["incidents"][0]
    assert incident["classification"]["support_code"] == "FAIQ-HA-RECORDER-001"
    assert incident["occurrences"] == 2
    assert incident["evidence"]["limit_exceeded"] is True
    assert incident["evidence"]["recorder_limit_bytes"] == RECORDER_ATTRIBUTE_LIMIT_BYTES


def test_warning_band_has_separate_support_code():
    monitor = RuntimeHealthMonitor()
    monitor.observe_attribute_payload(
        "status", _payload_over(ATTRIBUTE_WARNING_BYTES), recorder_exposed=True
    )
    incident = monitor.snapshot["incidents"][0]
    assert incident["classification"]["support_code"] == "FAIQ-HA-ATTR-SIZE-001"
    assert incident["classification"]["severity"] == "medium"


def test_unknown_exception_does_not_store_message_or_trace():
    monitor = RuntimeHealthMonitor()
    monitor.record_exception("coordinator", "update", RuntimeError("secret entity sensor.private"))
    snapshot = monitor.snapshot
    encoded = str(snapshot)
    assert "secret entity" not in encoded
    assert "sensor.private" not in encoded
    assert snapshot["incidents"][0]["classification"]["error_type"] == "RuntimeError"


def test_runtime_incident_participates_in_errors_mode_fingerprint():
    monitor = RuntimeHealthMonitor()
    monitor.record_exception("coordinator", "update", ValueError("private"))
    fingerprint = problem_fingerprint({"runtime_health": monitor.snapshot})
    assert fingerprint is not None


def test_release_version_is_025123():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert f'VERSION = "{CURRENT_RELEASE_VERSION}"' in (root / "custom_components/freshairiq/const.py").read_text()
    assert f'"version": "{CURRENT_RELEASE_VERSION}"' in (root / "custom_components/freshairiq/manifest.json").read_text()


def test_payload_size_fails_closed_for_circular_value():
    circular = []
    circular.append(circular)
    assert json_payload_bytes(circular) == 0


def test_datetime_stamp_and_bounded_incident_capacity():
    from datetime import datetime, timezone
    monitor = RuntimeHealthMonitor()
    stamp = datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc)
    for index in range(33):
        monitor.record_exception("coordinator", f"operation_{index}", RuntimeError("private"), stamp)
    snapshot = monitor.snapshot
    assert snapshot["incident_count"] == 32
    assert all(row["last_seen_at"] == stamp.isoformat() for row in snapshot["incidents"])
