from custom_components.freshairiq.runtime_health import HEALTH_CONTRACT_VERSION, RuntimeHealthMonitor


def test_metric_baseline_stays_quiet_for_normal_samples():
    monitor = RuntimeHealthMonitor()
    for value in (100, 102, 98, 101, 99, 103, 97, 100, 101):
        monitor.observe_metric("coordinator_update_ms", value, "2026-09-28T10:00:00+02:00", unit="ms")
    snap = monitor.snapshot
    assert HEALTH_CONTRACT_VERSION == 1
    assert snap["health_contract_version"] == 1
    assert snap["metric_baselines"][0]["samples"] == 9
    assert not [x for x in snap["incidents"] if x["classification"].get("category") == "runtime_anomaly"]


def test_metric_baseline_detects_large_regression_without_raw_samples():
    monitor = RuntimeHealthMonitor()
    for value in (100, 101, 99, 102, 98, 100, 101, 99, 100):
        monitor.observe_metric("coordinator_update_ms", value, "2026-09-28T10:00:00+02:00", unit="ms")
    monitor.observe_metric("coordinator_update_ms", 500, "2026-09-28T10:01:00+02:00", unit="ms")
    snap = monitor.snapshot
    incidents = [x for x in snap["incidents"] if x["classification"].get("category") == "runtime_anomaly"]
    assert len(incidents) == 1
    assert incidents[0]["classification"]["metric"] == "coordinator_update_ms"
    assert incidents[0]["evidence"]["ratio_to_baseline"] > 4
    assert "samples" not in incidents[0]["evidence"]


def test_health_snapshot_is_point_in_time_and_privacy_safe():
    monitor = RuntimeHealthMonitor()
    snap = monitor.health_snapshot("2026-09-28T10:02:00+02:00")
    assert snap["captured_at"] == "2026-09-28T10:02:00+02:00"
    assert snap["privacy"]["contains_exception_messages"] is False


def test_metric_probe_rejects_invalid_values_and_bounds_metric_cardinality():
    monitor = RuntimeHealthMonitor()
    for value in (None, -1, float("nan"), float("inf"), float("-inf")):
        monitor.observe_metric("invalid", value, "2026-09-28T10:03:00+02:00")
    assert monitor.snapshot["metric_baselines"] == []
    for index in range(24):
        monitor.observe_metric(f"metric_{index}", 1, "2026-09-28T10:03:00+02:00")
    monitor.observe_metric("metric_overflow", 1, "2026-09-28T10:03:00+02:00")
    assert len(monitor.snapshot["metric_baselines"]) == 24
