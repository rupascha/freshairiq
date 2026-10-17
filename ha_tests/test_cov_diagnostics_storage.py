"""Real-HA coverage for the rolling diagnostics recorder and the learning store.

The recorder writes real JSONL files below a temporary Home Assistant config
directory; the learning store loads corrupt persisted data through Home
Assistant's real ``Store`` (``hass_storage``).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.util import dt as dt_util

from custom_components.freshairiq import diagnostics as diag
from custom_components.freshairiq.const import DOMAIN, LEGACY_DOMAIN, STORAGE_KEY
from custom_components.freshairiq.diagnostics import (
    FreshAirIQDiagnosticsRecorder,
    _compact_learning_components,
    _json_safe,
    _latest_evidence,
    _longest_consecutive_day_streak,
    _privacy_safe_decision,
    _privacy_safe_iq_state,
    _sanitise_client_context,
    _three_state_learning_diagnostic,
    async_get_config_entry_diagnostics,
)
from custom_components.freshairiq.storage import LearningStore, _finite_number

CLIENT_ID = "faiq-client-" + "abcdef123456"


@pytest.fixture
async def cfg(hass, tmp_path) -> Path:
    hass.config.config_dir = str(tmp_path)
    await hass.config.async_set_time_zone("Europe/Berlin")
    return tmp_path


def _recorder(hass, entry_id: str = "entry1") -> FreshAirIQDiagnosticsRecorder:
    return FreshAirIQDiagnosticsRecorder(hass, entry_id, "9.9.9")


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# =========================================================================== pure helpers


def test_evidence_compaction_and_json_safety() -> None:
    assert _latest_evidence([{"a": 1}, {"a": 2}]) == {"a": 2}
    assert _latest_evidence([]) == {}
    assert _latest_evidence("x") == {}
    compact = _latest_evidence({"history": [1, 2, 3], "entries": [], "rate": 0.1})
    assert compact == {"rate": 0.1, "history_count": 3, "latest_history": 3, "entries_count": 0, "latest_entrie": None}
    assert _compact_learning_components([{"samples": [1]}, 5]) == [{"samples_count": 1, "latest_sample": 1}, 5]
    assert _compact_learning_components({"bath": {"records": [7]}, "n": 1}) == {"bath": {"records_count": 1, "latest_record": 7}, "n": 1}
    assert _compact_learning_components(3) == {}
    when = datetime(2026, 10, 15, 12, 0)
    assert _json_safe((1, float("nan"), {2: when})) == [1, None, {"2": "2026-10-15T12:00:00"}]
    assert _json_safe({1}) == [1]
    assert _json_safe(Path("/x")) == "/x"


def test_client_context_whitelist_rejects_and_bounds_values() -> None:
    assert _sanitise_client_context("ua") == {}
    assert _sanitise_client_context({"client_id": ""}) == {}
    assert _sanitise_client_context({"client_id": "device-abcdef123456"}) == {}
    assert _sanitise_client_context({"client_id": "faiq-client-short"}) == {}
    assert _sanitise_client_context({"client_id": "faiq-client-abc$def123456"}) == {}
    safe = _sanitise_client_context({
        "client_id": "faiq-client-session-abcdef123456",
        "platform_family": "PlayStation", "device_class": "fridge",
        "device_pixel_ratio": 99, "touch_points": "many",
        "viewport_css_px": {"width": "wide", "height": 1}, "screen_css_px": {"width": 50000, "height": 10},
        "user_agent": "Mozilla/5.0 secret",
    })
    assert safe["client_id"] == "faiq-client-session-abcdef123456"
    assert safe["platform_family"] == "Other" and safe["device_class"] == "other"
    assert safe["device_pixel_ratio"] is None and safe["touch_points"] is None
    assert safe["viewport_css_px"] is None and safe["screen_css_px"] is None
    assert "user_agent" not in safe


def test_streak_and_privacy_filters() -> None:
    assert _longest_consecutive_day_streak(["bad", None]) == 0
    assert _longest_consecutive_day_streak(["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "x"]) == 3
    assert _privacy_safe_decision("x") == {}
    assert _privacy_safe_iq_state(None) == {}
    assert _privacy_safe_iq_state({"summary": "Hi Anna", "decision": {"title": "t", "kind": "ventilate"}}) == {"decision": {"kind": "ventilate"}}
    result = _three_state_learning_diagnostic({"opening_learning": ["broken"], "three_state_contacts": ["binary_sensor.secret"]}, {})
    assert result["available"] is True and result["proven_contact_count"] == 1
    assert "binary_sensor.secret" not in json.dumps(result)


# =========================================================================== identity / clients


async def test_identity_is_recreated_from_invalid_files_and_storage_errors(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    recorder.directory.mkdir(parents=True)
    recorder._identity_path.write_text("[1, 2]", encoding="utf-8")
    first = await recorder.async_get_identity()
    # An unusable (non-object / undecodable) file is reported as recreated (A-22).
    assert first["identity_status"] == "recreated_invalid_identity"
    assert first["installation_id"].startswith("faiq-install-")

    recorder._identity_path.write_text("{broken", encoding="utf-8")
    broken_json = await recorder.async_get_identity()
    assert broken_json["identity_status"] == "recreated_invalid_identity"
    assert broken_json["installation_id"] != first["installation_id"]

    recorder._identity_path.write_text(json.dumps({"installation_id": "foreign-id", "export_sequence": "x"}), encoding="utf-8")
    second = await recorder.async_get_identity()
    assert second["identity_status"] == "recreated_invalid_identity"
    assert second["installation_id"].startswith("faiq-install-")

    third = await recorder.async_get_identity()
    assert third == {**third, "identity_status": "existing", "installation_id": second["installation_id"]}

    def broken(*_args):
        raise PermissionError("read-only")

    monkeypatch.setattr(recorder, "_load_or_create_field_test_identity", broken)
    assert await recorder.async_get_identity() == {"installation_id": None, "identity_status": "storage_error:PermissionError"}


async def test_client_registration_recovers_corrupt_registry(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    assert await recorder.async_register_client({"client_id": "nope"}) == {"registered": False, "reason": "invalid_client_context"}
    recorder.directory.mkdir(parents=True, exist_ok=True)
    recorder._clients_path.write_text("{not json", encoding="utf-8")
    result = await recorder.async_register_client({"client_id": CLIENT_ID, "browser_family": "Safari", "os_version": "18.1"})
    assert result == {"registered": True, "client_id": CLIENT_ID}
    rows = json.loads(recorder._clients_path.read_text())["clients"]
    assert rows[0]["seen_count"] == 1 and rows[0]["browser_family_history"] == ["Safari"]

    recorder._clients_path.write_text(json.dumps({"clients": "broken"}), encoding="utf-8")
    assert recorder._load_field_test_clients() == []

    def broken(*_args):
        raise OSError("disk gone")

    monkeypatch.setattr(recorder, "_register_client_sync", broken)
    assert await recorder.async_register_client({"client_id": CLIENT_ID}) == {"registered": False, "reason": "OSError: disk gone"}


async def test_runtime_environment_falls_back_for_unusable_system_info(hass, cfg, monkeypatch) -> None:
    import homeassistant.helpers.system_info as system_info

    async def weird(_hass):
        return ["not", "a", "dict"]

    monkeypatch.setattr(system_info, "async_get_system_info", weird)
    env = await _recorder(hass)._async_runtime_environment()
    assert set(env) == {"home_assistant_version", "python_version", "os_name", "os_version", "architecture", "python_implementation"}


# =========================================================================== configuration snapshot / records


async def test_configuration_snapshot_handles_odd_room_shapes(hass, cfg) -> None:
    recorder = _recorder(hass)
    now = dt_util.now()
    entry_data = {"rooms": [
        "garbage",
        {"key": "bath", "name": "Bad", "contact": "binary_sensor.bath_window",
         "contact_orientations": ["north"], "contact_covers": {"binary_sensor.bath_window": "cover.bath"}},
    ]}
    recorder.update_configuration_snapshot(entry_data, {"start_rh": 60, "notify_targets": ["notify.secret"]}, {"rooms": []}, now)
    snapshot = recorder._config_snapshot
    text = json.dumps(snapshot)
    assert "binary_sensor.bath_window" not in text and "cover.bath" not in text and "notify.secret" not in text
    room = next(row for row in snapshot["rooms"] if isinstance(row, dict) and row.get("key") == "bath") if isinstance(snapshot.get("rooms"), list) else None
    assert room is not None
    assert room["openings"][0]["cover_count"] == 1
    assert room["openings"][0]["orientation"] is None
    assert recorder._configuration_changed is False
    recorder.update_configuration_snapshot({"rooms": "x"}, {"start_rh": 61}, {"rooms": "x"}, now)
    assert recorder._configuration_changed is True


def _house(rooms: Any, **extra: Any) -> dict[str, Any]:
    return {"status": "ok", "intelligent_recommendation": {"kind": "none", "room_keys": []}, "rooms": rooms, **extra}


async def test_record_reasons_window_events_and_file_rows(hass, cfg) -> None:
    recorder = _recorder(hass)
    t0 = dt_util.now().replace(microsecond=0)
    store = {"rooms": {"bath": {"recommendation_followed": 3, "opening_learning": {"open": {"rate": 0.05, "samples": 2}}}, "junk": 1},
             "notification_diagnostics": [{"ok": True}]}
    bath_closed = {"name": "Bad", "active": False, "humidity": 70, "data_quality": "ok", "contact_orientations": {"binary_sensor.x": "south"}}

    # First record: full baseline (state_change without previous signature).
    assert await recorder.async_record(_house({"bath": bath_closed, "bad": "x"}), store, t0) is True
    # Unchanged within the idle interval: nothing written.
    assert await recorder.async_record(_house({"bath": bath_closed}), store, t0 + timedelta(minutes=1)) is False
    # Window opens -> window_event (full record).
    bath_open = {**bath_closed, "active": True, "open_seconds": 0}
    assert await recorder.async_record(_house({"bath": bath_open}), store, t0 + timedelta(minutes=2)) is True
    # Window closes -> event with measured duration.
    assert await recorder.async_record(_house({"bath": bath_closed}), store, t0 + timedelta(minutes=7)) is True
    # Completed session wins over any other reason.
    assert await recorder.async_record(_house({"bath": bath_closed}), store, t0 + timedelta(minutes=8), [{"recommendation_followed": True}, "junk"]) is True
    # Configuration change.
    recorder._configuration_changed = True
    assert await recorder.async_record(_house({"bath": bath_closed}), store, t0 + timedelta(minutes=9)) is True
    # Decision change after a baseline -> compact decision event.
    changed = _house({"bath": {**bath_closed, "action": "Ventilate"}})
    assert await recorder.async_record(changed, store, t0 + timedelta(minutes=10)) is True
    # Idle sample after the interval.
    assert await recorder.async_record(changed, store, t0 + timedelta(minutes=30)) is True
    # Non-dict room maps are tolerated everywhere.
    assert await recorder.async_record(_house("broken"), {"rooms": "broken"}, t0 + timedelta(minutes=31)) is True

    rows = _lines(recorder.directory / f"{t0.date().isoformat()}.jsonl")
    reasons = [row["reason"] for row in rows]
    assert reasons == ["state_change", "window_event", "window_event", "session_completed", "configuration_changed",
                       "state_change", "idle_sample", "state_change"]
    assert rows[1]["window_events"][0]["event"] == "ventilation_opened"
    closed = rows[2]["window_events"][0]
    assert closed["event"] == "ventilation_closed" and closed["duration_seconds"] == 300.0
    assert rows[5]["record_type"] == "decision_event"
    assert rows[0]["rooms"][0]["contact_orientations"] == ["south"]
    assert rows[0]["rooms"][0]["recommendation_followed"] == 3
    assert "binary_sensor.x" not in json.dumps(rows)
    assert recorder.status["records_this_runtime"] == 8
    assert recorder.status["last_error"] is None


async def test_window_event_duration_with_unusable_start_and_removed_rooms(hass, cfg) -> None:
    recorder = _recorder(hass)
    now = dt_util.now()
    assert recorder._window_events({"rooms": "x"}, now) == []
    assert recorder._window_events({"rooms": {"a": {"active": True}, "b": {"active": False}, "c": 5}}, now) == []
    recorder._last_room_opened_at["a"] = "yesterday"
    events = recorder._window_events({"rooms": {"a": {"active": False}}}, now)
    assert events[0]["event"] == "ventilation_closed" and "duration_seconds" not in events[0]
    assert "b" not in recorder._last_room_active
    # Naive "now" against an aware opening timestamp is tolerated as well.
    recorder._window_events({"rooms": {"a": {"active": True}}}, now)
    events = recorder._window_events({"rooms": {"a": {"active": False}}}, now.replace(tzinfo=None))
    assert "duration_seconds" not in events[0]


def test_sensor_quality_summary_counts_issue_classes() -> None:
    summary = FreshAirIQDiagnosticsRecorder._sensor_quality_summary({"rooms": {
        "a": {"data_quality": "ok"},
        "b": {"data_quality": "stale", "measurement_frame_reason": "Temp-Frame old", "frame_age_temp_s": "x", "frame_age_humidity_s": None},
        "c": {"data_quality": "stale", "frame_age_temp_s": 120},
        "d": {"data_quality": "missing", "frame_age_humidity_s": 900},
        "e": {"data_quality": "warn", "frame_age_temp_s": 10},
        "f": {"monitor_only": True},
    }, "sensor_recovery": {"active": True, "required_sources_unavailable": 2}})
    assert summary["rooms_total"] == 5 and summary["rooms_monitor_only"] == 1
    assert summary["issue_age_buckets"] == {"60_300s": 1, "gt_300s": 1, "lt_60s": 1, "unknown": 1}
    assert summary["issue_reason_counts"]["temp_frame_old"] == 1
    assert summary["sensor_recovery_active"] is True and summary["sensor_recovery_unavailable_sources"] == 2


async def test_record_write_failures_are_reported(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)

    def broken(_path, _line):
        raise OSError("disk full")

    monkeypatch.setattr(recorder, "_append_line", broken)
    assert await recorder.async_record(_house({}), {}, dt_util.now()) is False
    assert recorder.last_error == "OSError: disk full"
    assert await recorder.async_record_room_creation_trace({"step": "x"}) is False
    assert await recorder.async_record_flow_error({"error_type": "KeyError"}) is False
    assert recorder.record_count_session == 0


async def test_flow_error_and_room_creation_trace_rows(hass, cfg) -> None:
    recorder = _recorder(hass)
    assert await recorder.async_record_flow_error({"error_type": "KeyError", "step": "room"}) is True
    assert await recorder.async_record_room_creation_trace({"room_digest": "abc", "stage": "created"}) is True
    rows = _lines(next(recorder.directory.glob("*.jsonl")))
    assert [row["record_type"] for row in rows] == ["config_flow_error", "room_creation_trace"]
    assert rows[0]["error_type"] == "KeyError" and rows[0]["freshairiq_version"] == "9.9.9"
    assert recorder.record_count_session == 2


def test_full_and_trend_records_tolerate_non_dict_rooms(hass) -> None:
    recorder = FreshAirIQDiagnosticsRecorder(hass, "x", "1")
    now = dt_util.now()
    record = recorder._build_record(_house("broken"), {"rooms": "broken"}, now, "state_change", [])
    assert record["rooms"] == [] and record["reason"] == "state_change"
    record = recorder._build_record(_house({"a": "x", "b": {"humidity": 50}}), {"rooms": {"b": "x"}}, now, "state_change", [])
    assert [room["key"] for room in record["rooms"]] == ["b"]
    trend = recorder._build_trend_record(_house({"a": "x", "b": {"humidity": 50}}), now, "idle_sample")
    assert trend["rooms"] == [{"key": "b", "humidity": 50}]


# =========================================================================== legacy compaction / cleanup


def test_compact_legacy_record_variants() -> None:
    compact = FreshAirIQDiagnosticsRecorder._compact_legacy_record
    event = {"record_type": "event", "reason": "periodic"}
    assert compact(event) is event
    assert compact({"reason": "periodic", "window_events": [1]}) == {"reason": "periodic", "window_events": [1]}
    assert compact({"reason": "flow"}) == {"reason": "flow"}
    out = compact({"reason": "state_change", "rooms": [{"key": None, "humidity": 60}, {"name": "x", "key": "k"}],
                   "configuration_snapshot": {"a": 1}, "house": {}, "decision": {"kind": "none"}})
    assert out["record_type"] == "trend_legacy_compacted"
    assert out["configuration_snapshot"] == {"a": 1}
    assert out["rooms"][0] == {"key": None, "humidity": 60}
    out = compact({"reason": "periodic", "rooms": [{"humidity": 60}, {"name": "secret", "key_alias": "k", "key": 0}]})
    assert out["rooms"][1] == {"key": 0}


async def test_cleanup_retention_legacy_compaction_and_size_cap(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    now = dt_util.now()
    directory = recorder.directory
    directory.mkdir(parents=True)
    # Nothing to do without a directory.
    other = _recorder(hass, "other")
    other.directory = directory / "missing"
    other._cleanup_files(now)

    old = directory / f"{(now.date() - timedelta(days=40)).isoformat()}.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    (directory / "notes.jsonl").write_text("{}\n", encoding="utf-8")
    yesterday = directory / f"{(now.date() - timedelta(days=1)).isoformat()}.jsonl"
    legacy = {"reason": "periodic", "rooms": [{"key": "bath", "humidity": 60, "name": "Bad", "contacts": ["x"]}], "house": {}}
    yesterday.write_text("\n".join(["", json.dumps(legacy), "{broken", json.dumps({"record_type": "event", "reason": "x"})]) + "\n", encoding="utf-8")
    unchanged = directory / f"{(now.date() - timedelta(days=2)).isoformat()}.jsonl"
    unchanged.write_text(json.dumps({"record_type": "trend", "reason": "idle_sample"}) + "\n", encoding="utf-8")
    today = directory / f"{now.date().isoformat()}.jsonl"
    today.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    recorder._cleanup_files(now)
    assert not old.exists()
    rows = yesterday.read_text(encoding="utf-8").splitlines()
    assert json.loads(rows[0])["record_type"] == "trend_legacy_compacted"
    assert rows[1] == "{broken"
    assert json.loads(rows[2])["record_type"] == "event"
    assert json.loads(today.read_text())["reason"] == "periodic" and "record_type" not in json.loads(today.read_text())
    cached = dict(recorder._legacy_compaction_mtime_ns)
    assert str(yesterday) in cached

    # Second run hits the mtime cache; the size cap then removes the oldest days.
    monkeypatch.setattr(diag, "DIAGNOSTICS_MAX_TOTAL_BYTES", today.stat().st_size + 1)
    recorder._cleanup_files(now)
    assert today.exists()
    assert not unchanged.exists() and not yesterday.exists()


async def test_compaction_io_errors_keep_original_file(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    recorder.directory.mkdir(parents=True)
    path = recorder.directory / "2026-01-01.jsonl"
    recorder._compact_legacy_file(path)  # missing file: read error is ignored
    path.write_text(json.dumps({"reason": "periodic", "rooms": []}) + "\n", encoding="utf-8")
    original = path.read_text()
    real_write = Path.write_text

    def failing_write(self, *args, **kwargs):
        if self.suffix == ".tmp":
            raise OSError("no space")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)
    recorder._compact_legacy_file(path)
    assert path.read_text() == original
    assert not path.with_suffix(".jsonl.tmp").exists()


async def test_cleanup_tolerates_stat_errors(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    now = dt_util.now()
    recorder.directory.mkdir(parents=True)
    victim = recorder.directory / f"{(now.date() - timedelta(days=3)).isoformat()}.jsonl"
    victim.write_text(json.dumps({"record_type": "trend"}) + "\n", encoding="utf-8")
    real_stat = Path.stat
    plan: list[bool] = []  # True = fail; consumed per stat() of the victim, default ok

    def flaky_stat(self, *args, **kwargs):
        if self == victim and plan and plan.pop(0):
            raise OSError("stat failed")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    monkeypatch.setattr(diag, "DIAGNOSTICS_MAX_TOTAL_BYTES", -1)
    plan[:] = [True] * 10  # every stat fails: no compaction, no size accounting, no deletion
    recorder._cleanup_files(now)
    assert str(victim) not in recorder._legacy_compaction_mtime_ns
    assert victim.exists()
    plan[:] = [False, True, True, True, True]  # stat after compaction fails, size stats fail
    recorder._cleanup_files(now)
    assert str(victim) not in recorder._legacy_compaction_mtime_ns


# =========================================================================== export


async def test_export_summarises_records_and_reports_damage(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    recorder.directory.mkdir(parents=True)
    day1 = recorder.directory / "2026-10-13.jsonl"
    day2 = recorder.directory / "2026-10-14.jsonl"
    day1.write_text("\n".join([
        json.dumps({"timestamp": "2026-10-13T10:00:00+02:00", "reason": "periodic", "record_type": "trend", "freshairiq_version": "1",
                    "forecast_validation": {"mae": 1}, "runtime_environment": {"home_assistant_version": "2026.10.1"}}),
        "",
        "[1]",
        "{bad",
        json.dumps({"timestamp": "garbage", "reason": "x", "record_type": "trend", "configuration_snapshot": {"captured_at": "x", "a": 1}}),
    ]) + "\n", encoding="utf-8")
    day2.write_text("\n".join([
        json.dumps({"timestamp": "2026-10-14T10:00:00", "reason": "session_completed", "freshairiq_version": "2",
                    "completed_sessions": [{"recommendation_followed": True}, "junk"],
                    "forecast_backtest": {"n": 2}, "learning_effectiveness": {"x": 1}, "forecast_validation": {"mae": 2}}),
        json.dumps({"timestamp": "2026-10-14T11:00:00", "reason": "periodic", "record_type": "trend", "completed_sessions": "bad"}),
    ]) + "\n", encoding="utf-8")
    recorder._clients_path.write_text("{bad", encoding="utf-8")

    exported = await recorder.async_export()
    assert exported["record_count"] == 4
    assert sorted(exported["read_errors"]) == ["2026-10-13.jsonl:3:non_object", "2026-10-13.jsonl:4"]
    field_test = exported["field_test"]
    assert field_test["known_clients"] == []
    assert field_test["observation"]["calendar_days_with_records"] == 2
    assert field_test["observation"]["largest_sampling_gap_minutes"] == 1440.0
    assert [row["version"] for row in field_test["home_assistant_version_history"]] == ["2026.10.1"]
    assert len(field_test["configuration_history"]) == 1
    assert field_test["observation"]["truncated"] is False

    # Record cap and identity storage error.
    monkeypatch.setattr(diag, "DIAGNOSTICS_MAX_EXPORT_RECORDS", 2)

    def broken_identity(_now):
        raise PermissionError("ro")

    monkeypatch.setattr(recorder, "_load_or_create_field_test_identity", broken_identity)
    capped = recorder._export_sync(dt_util.now())
    assert capped["record_count"] == 2 and capped["truncated"] is True
    assert capped["field_test"]["identity_status"] == "storage_error:PermissionError"
    assert [r["timestamp"] for r in capped["records"]] == ["2026-10-14T10:00:00", "2026-10-14T11:00:00"]


async def test_export_byte_cap_and_unreadable_day(hass, cfg, monkeypatch) -> None:
    recorder = _recorder(hass)
    recorder.directory.mkdir(parents=True)
    (recorder.directory / "2026-10-12.jsonl").mkdir()  # unreadable as a file
    (recorder.directory / "2026-10-14.jsonl").write_text(
        json.dumps({"timestamp": "2026-10-14T01:00:00", "reason": "x", "record_type": "trend"}) + "\n"
        + json.dumps({"timestamp": "2026-10-14T02:00:00", "reason": "y", "record_type": "trend", "pad": "z" * 400}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(diag, "DIAGNOSTICS_MAX_EXPORT_BYTES", 300)
    exported = recorder._export_sync(dt_util.now())
    assert exported["record_count"] == 0
    assert exported["truncated"] is True
    monkeypatch.setattr(diag, "DIAGNOSTICS_MAX_EXPORT_BYTES", 10_000)
    exported = recorder._export_sync(dt_util.now())
    assert exported["record_count"] == 2
    assert "2026-10-12.jsonl" in exported["read_errors"]


# =========================================================================== native HA diagnostics


async def test_config_entry_diagnostics_omits_identifiers(hass, cfg) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={"rooms": []})
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(version="9.9.9", data={"status": "ok", "rooms": {
        "bath": {"name": "Bad", "humidity": 61.0, "temperature": float("inf"), "entity_id": "sensor.bath", "action": "Ventilate"},
        "junk": "x",
    }})
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["freshairiq_version"] == "9.9.9"
    assert result["house_status"] == "ok"
    assert result["rooms"] == [{**{k: None for k in result["rooms"][0]}, "name": "Bad", "humidity": 61.0, "action": "Ventilate"}]
    assert "sensor.bath" not in json.dumps(result)

    entry.runtime_data = SimpleNamespace(integration_version="1.0", data=None)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["freshairiq_version"] == "1.0" and result["rooms"] == [] and result["house_status"] is None


# =========================================================================== learning store


def _seed(hass_storage, key: str, data: dict[str, Any]) -> None:
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": data}


async def test_store_load_repairs_corrupt_persistence(hass, hass_storage) -> None:
    _seed(hass_storage, f"{STORAGE_KEY}.e1", {
        "notification_diagnostics": "x", "night_observed_dates": "x", "ventilation_group": "x",
        "rooms": {"bad": "x", "bath": {
            "three_state_contacts": "x", "passage_behavior": [], "history": {
                "2026-10-01": {"sessions": 2, "moisture_measured_sessions": 1},
                "2026-10-02": {"sessions": 1},
                "garbage": {"sessions": 1},
                "2026-10-03": {"sessions": 0},
            },
            "strategy_outcome_samples": 4,
            "learning_observation_dates": ["2026-09-30", "nope"],
            "routine_source_buckets": {"a": {"last_seen": "2026-10-04T10:00:00"}, "b": "x", "c": {"last_seen": "x"}},
            "seasonal_source_profiles": {
                "winter": {"last_seen": "2026-01-15T12:00:00"}, "autumn": {"last_seen": "2026-10-05T08:00:00"},
                "spring": "x", "summer": {"last_seen": None}, "odd": {"last_seen": "2026-07-01 garbage"},
            },
            "seasonal_observation_days": "x",
            "shadow_learning_candidates": "x", "shadow_rollback_previous_factor": "nan",
            "shadow_rollback_active_error": -1, "forecast_source_ml_min": "inf",
        }},
        "history": [], "notifications": [], "water_daily": [], "house_strategy_buckets": [],
        "house_strategy_observation_dates": {}, "forecast_validation_history": {}, "post_close_stabilization_history": {},
        "night_model_ml_h": "nan", "night_model_samples": "x",
    })
    store = LearningStore(hass, "e1")
    await store.async_load()
    data = store.data
    assert data["notification_diagnostics"] == [] and data["night_observed_dates"] == []
    assert data["ventilation_group"] is None
    for key in ("history", "notifications", "water_daily", "house_strategy_buckets"):
        assert data[key] == {}
    for key in ("house_strategy_observation_dates", "forecast_validation_history", "post_close_stabilization_history"):
        assert data[key] == []
    assert data["night_model_ml_h"] is None and data["night_model_samples"] == 0
    assert data["rooms"]["bad"]["learning_rate"] == 0.03
    bath = data["rooms"]["bath"]
    assert bath["three_state_contacts"] == [] and bath["passage_behavior"] == {}
    assert bath["personal_context_observation_dates"] == ["2026-10-01", "2026-10-02"]
    assert bath["learning_observation_dates"] == ["2026-09-30", "2026-10-01"]
    assert bath["strategy_observation_dates"] == ["2026-10-01"]
    assert bath["routine_observation_dates"] == ["2026-10-04"]
    assert bath["seasonal_observation_days"] == {"2025:winter": ["2026-01-15"], "2026:autumn": ["2026-10-05"]}
    assert bath["time_evidence_migration_v025040"] is True
    assert bath["shadow_learning_candidates"] == {}
    assert bath["shadow_rollback_previous_factor"] is None
    assert bath["shadow_rollback_active_error"] == 0.0
    assert bath["forecast_source_ml_min"] is None


async def test_store_load_sessions_shape_and_legacy_migration(hass, hass_storage) -> None:
    _seed(hass_storage, f"{STORAGE_KEY}.e2", {"ventilation_group": {"sessions": "x"}})
    store = LearningStore(hass, "e2")
    await store.async_load()
    assert store.data["ventilation_group"]["sessions"] == []

    _seed(hass_storage, f"{LEGACY_DOMAIN}.learning.old", {"rooms": {"bath": {"learning_rate": 0.1}}})
    migrated = LearningStore(hass, "e3", legacy_entry_id="old")
    await migrated.async_load()
    assert migrated.data["rooms"]["bath"]["learning_rate"] == 0.1
    await hass.async_block_till_done()
    assert hass_storage[f"{STORAGE_KEY}.e3"]["data"]["rooms"]["bath"]["learning_rate"] == 0.1

    empty = LearningStore(hass, "e4", legacy_entry_id="never")
    await empty.async_load()
    assert empty.data["rooms"] == {}


async def test_store_water_series_and_points_tolerate_corruption(hass, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    store = LearningStore(hass, "w")
    now = dt_util.now()
    store.data["water_last_sample_at"] = "garbage"
    store.data["water_daily"] = []
    assert store.record_house_water(now, 500) is True
    assert store.record_house_water(now + timedelta(seconds=10), 900) is False
    store.data["water_daily"][now.date().isoformat()] = "x"
    assert store.record_house_water(now + timedelta(minutes=2), 700) is True
    assert store.data["water_daily"][now.date().isoformat()] == {"sum_ml": 700.0, "samples": 1, "mean_ml": 700.0}
    store.data["water_daily"]["2026-10-14"] = "x"
    history = store.water_history_days(3)
    assert [row["water_ml"] for row in history] == [0, 0, 700]
    store.data["water_daily"] = {
        "2026-10-12": {"mean_ml": 1000, "samples": 4}, "2026-10-13": {"mean_ml": 1100, "samples": 4},
        "2026-10-14": {"mean_ml": 1000, "samples": 4}, "2026-10-15": {"mean_ml": 1010, "samples": 4},
    }
    assert [row["trend"] for row in store.water_history_days(4)] == ["stable", "wetter", "trockener", "stabil"]
    store.data["water_daily"] = "x"
    assert store.water_history_days(1)[0]["samples"] == 0

    store.room("bath")["temperature_points"] = "x"
    assert store.record_room_temperature_point("bath", now, 21.0) is True
    assert store.record_room_temperature_point("bath", now, 21.5) is False
    hour = now.strftime("%Y-%m-%dT%H:00")
    assert store.room("bath")["temperature_points"] == [{"time": hour, "temperature_c": 21.5}]
    store.room("bath")["humidity_points"] = "x"
    assert store.record_room_humidity_point("bath", now, 55.0) is True
    assert store.record_room_humidity_point("bath", now, "nan") is False
    store.room("bath")["humidity_points"].insert(0, {"time": "garbage"})
    store.room("bath")["humidity_points"].insert(0, {"time": "2026-01-01T00:00"})
    assert store.record_room_humidity_point("bath", now + timedelta(hours=1), 56.0) is True
    assert [p["time"] for p in store.room("bath")["humidity_points"]] == [hour, (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")]
    store.room("bath")["humidity_points"].append({"no_time": 1})
    store.room("bath")["humidity_points"].append({"time": "bad"})
    assert [p["humidity_percent"] for p in store.room_humidity_points("bath", 2)] == [0.0, 56.0]

    store.room("bath")["history"] = "x"
    assert len(store.room_history_days("bath", 2)) == 2
    store.data["temperature_points"] = "x"
    assert store.record_temperature_point(now, 18.0) is True
    assert store.record_temperature_point(now, 18.4) is False
    assert store.data["temperature_points"] == [{"time": hour, "temperature_c": 18.4}]
    assert _finite_number("abc", 7.0) == 7.0
    assert _finite_number(float("inf"), 1.0) == 1.0


async def test_store_room_access_repairs_wrong_container_types(hass, hass_storage) -> None:
    _seed(hass_storage, f"{STORAGE_KEY}.r", {"rooms": ["not", "a", "dict"]})
    store = LearningStore(hass, "r")
    await store.async_load()
    assert store.data["rooms"] == {}
    room = store.room("bath")
    room.update({"three_state_contacts": "x", "passage_behavior": [], "session_passage_contacts": {},
                 "shadow_learning_candidates": [], "learning_rate": 5, "opening_learning": {"open": {"rate": "nan"}}})
    again = store.room("bath")
    assert again is room
    assert room["three_state_contacts"] == [] and room["passage_behavior"] == {}
    assert room["session_passage_contacts"] == [] and room["shadow_learning_candidates"] == {}
    assert room["learning_rate"] == 0.25
    assert room["opening_learning"]["open"] == {"rate": 0.03, "samples": 0, "credit": 0.0}


async def test_store_prune_repairs_non_dict_rooms(hass, freezer) -> None:
    freezer.move_to("2026-10-15T12:00:00+02:00")
    store = LearningStore(hass, "p")
    store.data["rooms"] = {"broken": "x", "bath": {"history": {"2020-01-01": {}, "2026-10-14": {"sessions": 1}, "bad": {}}}}
    store.data["history"] = "x"
    store.prune(30)
    assert store.data["history"] == {}
    assert store.data["rooms"]["broken"]["history"] == {}
    assert store.data["rooms"]["bath"]["history"] == {"2026-10-14": {"sessions": 1}}
