"""F38 regressions: runtime metric anomalies recover; lasting slowdowns stay active.

Synthetic series reproduce the documented isolated execution of the work order
(20 baseline values 10/11 ms -> 100 ms spike -> 50 values 10/11 ms kept one
active incident with healthy_confirmations=0 in 0.26.5.0).
"""
from __future__ import annotations

from custom_components.freshairiq.runtime_health import RuntimeHealthMonitor


def _feed(monitor, values, metric="coordinator_phase_core_ms", unit="ms"):
    for index, value in enumerate(values):
        monitor.observe_metric(metric, value, f"2026-10-16T00:{index // 60:02d}:{index % 60:02d}+00:00", unit=unit)


def _anomaly(monitor):
    rows = [r for r in monitor.snapshot["incidents"] if r["classification"]["category"] == "runtime_anomaly"]
    assert len(rows) <= 1
    return rows[0] if rows else None


def test_single_spike_is_kept_as_history_and_resolves_after_recovery():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100])
    assert _anomaly(monitor)["status"] == "active"
    _feed(monitor, [10, 11] * 25)
    row = _anomaly(monitor)
    assert row["status"] == "resolved"
    assert row["resolved_at"] is not None
    assert row["occurrences"] == 1  # history retained
    assert monitor.snapshot["active_incident_count"] == 0
    assert monitor.user_summary["active_problem"] is False


def test_recovery_needs_ten_consecutive_normal_samples():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100] + [10] * 9)
    assert _anomaly(monitor)["status"] == "active"
    _feed(monitor, [10])
    assert _anomaly(monitor)["status"] == "resolved"


def test_lasting_slowdown_stays_active():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100] * 60)
    row = _anomaly(monitor)
    assert row["status"] == "active"
    assert row["evidence"]["reference_mean"] < 12  # pre-incident baseline is kept


def test_recurrence_reactivates_the_same_incident():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100] + [10, 11] * 10)
    assert _anomaly(monitor)["status"] == "resolved"
    _feed(monitor, [200])
    row = _anomaly(monitor)
    assert row["status"] == "active" and row["occurrences"] == 2


def test_sub_millisecond_jitter_is_not_an_incident_but_real_delay_is():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [0.12, 0.13] * 10 + [1.444], metric="coordinator_phase_guardian_ms")
    assert _anomaly(monitor) is None
    _feed(monitor, [0.12, 0.13] * 10 + [750.0], metric="coordinator_phase_core_ms")
    assert _anomaly(monitor)["classification"]["metric"] == "coordinator_phase_core_ms"


def test_restart_starts_with_a_clean_baseline():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100])
    fresh = RuntimeHealthMonitor()  # coordinator creates a new monitor on (re)start
    _feed(fresh, [100] * 5)
    assert _anomaly(fresh) is None


def test_zero_or_tiny_baseline_without_unit_floor_is_unchanged():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [0.0] * 20 + [5.0], unit="")
    assert _anomaly(monitor) is None  # mean 0 -> ratio guard, as before


def test_incident_with_corrupt_evidence_is_kept_unchanged():
    monitor = RuntimeHealthMonitor()
    _feed(monitor, [10, 11] * 10 + [100])
    row = next(iter(monitor._incidents.values()))
    for corrupt in ({"reference_mean": "x"}, {"reference_mean": 0.0}, {}):
        row["evidence"] = dict(corrupt)
        _feed(monitor, [10] * 12)
        assert row["status"] == "active"
