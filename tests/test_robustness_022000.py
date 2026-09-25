"""Behavioural regression tests for the v0.25.0.7 robustness foundation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import inf, nan
from pathlib import Path

from custom_components.freshairiq.robustness import (
    RobustnessMonitor,
    finite_float,
    prepare_runtime_rooms,
    safe_options,
)

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_finite_float_rejects_nan_inf_and_bad_types():
    assert finite_float(nan, 1.0) == 1.0
    assert finite_float(inf, 2.0) == 2.0
    assert finite_float("broken", 3.0) == 3.0
    assert finite_float("4.25") == 4.25


def test_safe_options_repairs_only_invalid_numeric_values():
    defaults = {"threshold": 2.5, "samples": 10, "enabled": True, "mode": "comfort"}
    merged, repaired = safe_options(
        defaults,
        {"threshold": "nan", "samples": "12", "enabled": False, "mode": "custom"},
    )
    assert merged["threshold"] == 2.5
    assert merged["samples"] == 12
    assert merged["enabled"] is False
    assert merged["mode"] == "custom"
    assert repaired == ["threshold"]


def test_prepare_runtime_rooms_isolates_malformed_room_and_repairs_nonfatal_fields():
    rooms, issues = prepare_runtime_rooms([
        {"key": "living", "name": "Living", "volume": 55, "sort_order": 2},
        "corrupt",
        {"key": "badvolume", "name": "Bad volume", "volume": float("nan"), "sort_order": "x"},
        {"name": "No key", "volume": 20},
        {"key": "living", "name": "Duplicate", "volume": 20},
    ])
    assert [room["key"] for room in rooms] == ["living", "badvolume"]
    assert rooms[1]["volume"] == 0.0
    assert rooms[1]["sort_order"] == 9999
    assert "room_1:not_a_mapping" in issues
    assert "room:badvolume:invalid_volume" in issues
    assert "room_3:missing_key" in issues
    assert "room_4:duplicate_key:living" in issues


def test_robustness_monitor_resets_failure_streak_after_success():
    monitor = RobustnessMonitor()
    started = datetime.now(timezone.utc) - timedelta(milliseconds=10)
    monitor.failure(started, ValueError("test"))
    monitor.failure(started, TypeError("test"))
    assert monitor.consecutive_failures == 2
    assert monitor.refresh_failures == 2
    assert monitor.last_failure_type == "TypeError"
    monitor.success(started)
    snap = monitor.snapshot()
    assert snap["consecutive_failures"] == 0
    assert snap["refresh_successes"] == 1
    assert snap["last_update_duration_ms"] >= 0


def test_coordinator_has_fail_closed_update_wrapper_and_initialized_debounce_handle():
    text = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "self._refresh_coalesce_unsub = None" in text
    assert "except Exception as exc" in text
    assert "raise UpdateFailed(" in text
    assert "previous coordinator data is retained" in text
    assert 'data["runtime_robustness"] = self.robustness.snapshot()' in text


def test_runtime_data_is_the_single_config_entry_runtime_source():
    runtime = (COMP / "runtime.py").read_text(encoding="utf-8")
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert "entry.runtime_data = coordinator" in runtime
    assert "hass.data.setdefault(DOMAIN" not in runtime
    assert "set_runtime_coordinator(hass, entry, coordinator)" in init
    assert "clear_runtime_coordinator(hass, entry)" in init


def test_storage_hardening_guards_nonfinite_learning_state():
    text = (COMP / "storage.py").read_text(encoding="utf-8")
    assert "_sanitize_room_learning" in text
    assert "isfinite(number)" in text
    assert 'min(max(rate, 0.002), 0.25)' in text
    assert 'room["outcome_removed_factor"]' in text


def test_release_version_022000_is_consistent():
    assert 'VERSION = "0.25.0.76"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.76"' in (COMP / "manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.76";' in (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert (ROOT / "RELEASE_NOTES_0.25.0.0.md").exists()
