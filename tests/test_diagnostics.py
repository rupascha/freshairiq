"""Tests for the portable FreshAirIQ diagnostics recorder."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types

# diagnostics.py imports a very small Home Assistant surface.  Provide the
# minimal standalone test doubles before importing the module.
ha = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
components = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
http = types.ModuleType("homeassistant.components.http")
class HomeAssistantView:
    pass
http.HomeAssistantView = HomeAssistantView
sys.modules.setdefault("homeassistant.components.http", http)
core = types.ModuleType("homeassistant.core")
class HomeAssistant:
    pass
core.HomeAssistant = HomeAssistant
sys.modules.setdefault("homeassistant.core", core)
util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
dt = types.ModuleType("homeassistant.util.dt")
dt.now = datetime.now
sys.modules.setdefault("homeassistant.util.dt", dt)
util.dt = dt

from custom_components.freshairiq.diagnostics import (
    DIAGNOSTICS_RETENTION_DAYS,
    FreshAirIQDiagnosticsRecorder,
)


class _Config:
    def __init__(self, root: Path) -> None:
        self.root = root
    def path(self, *parts: str) -> str:
        return str(self.root.joinpath(*parts))


class _Hass:
    def __init__(self, root: Path) -> None:
        self.config = _Config(root)
    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _data(active: bool = False, quality: str = "ok") -> dict:
    return {
        "status": "ok",
        "outdoor_temperature": 12.3,
        "outdoor_humidity": 70.0,
        "outdoor_absolute_humidity": 7.4,
        "outdoor_data_quality": "ok",
        "heating_system": "gas",
        "energy_price_per_kwh": 0.11,
        "forecast_heat_kwh": 0.4,
        "forecast_cost": 0.05,
        "rooms": {
            "living": {
                "key": "living",
                "name": "Wohnzimmer",
                "floor": "ground_floor",
                "volume_m3": 75.0,
                "data_quality": quality,
                "active": active,
                "open_seconds": 180 if active else 0,
                "temperature": 21.2,
                "humidity": 61.0,
                "absolute_humidity": 11.3,
                "water_in_air_ml": 848,
                "contact_orientations": {"binary_sensor.private_window": "e"},
            }
        },
        "intelligent_recommendation": {"kind": "ventilate", "room_keys": ["living"]},
        "iq_state": {},
        "night_strategy": {},
        "day_night_plan": {},
        "future_weather_boundaries": {},
    }


def _store() -> dict:
    return {
        "iq_active_advice": {
            "signature": "ventilate|living",
            "room_keys": ["living"],
            "followed": True,
            "followed_room_keys": ["living"],
        },
        "rooms": {
            "living": {
                "learning_rate": 0.03,
                "learning_samples": 4,
                "learning_status": "Stable",
                "diagnosis": "Valid learning session",
                "recommendation_opportunities": 5,
                "recommendation_followed": 4,
                "recommendation_missed": 1,
                "recommendation_follow_rate": 80.0,
                "avg_follow_delay_min": 3.2,
            }
        },
    }


def test_retention_is_30_days():
    assert DIAGNOSTICS_RETENTION_DAYS == 30


def test_configuration_snapshot_is_anonymised(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry-secret", "0.18.2.0")
    entry_data = {
        "outdoor_weather": "weather.private_home",
        "pollen_entity": "sensor.private_pollen",
        "levels": ["EG"],
        "rooms": [{
            "key": "living", "name": "Wohnzimmer", "floor": "ground_floor", "volume": 75.0,
            "contacts": ["binary_sensor.private_window"],
            "contact_orientations": {"binary_sensor.private_window": "e"},
        }],
    }
    options = {
        "start_rh": 62.0,
        "heating_system": "gas",
        "adult_presence_entities": ["person.private_name"],
        "notification_targets": ["notify.private_phone"],
    }
    recorder.update_configuration_snapshot(entry_data, options, _data(), datetime(2026, 9, 10, 12, 0))
    text = str(recorder._config_snapshot)
    assert "weather.private_home" not in text
    assert "sensor.private_pollen" not in text
    assert "binary_sensor.private_window" not in text
    assert "person.private_name" not in text
    assert "notify.private_phone" not in text
    assert recorder._config_snapshot["capabilities"]["adult_presence_tracker_count"] == 1
    assert recorder._config_snapshot["rooms"][0]["contact_orientations"] == ["e"]


def test_record_contains_quality_window_and_recommendation_tracking(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    first = recorder._build_record(_data(False), _store(), now, "periodic", [])
    assert first["sensor_quality"]["room_quality_percent"] == 100.0
    assert first["window_events"] == []
    assert first["recommendation_tracking"]["active_advice"]["followed"] is True
    learning = first["learning"]["rooms"][0]
    assert learning["learning_rate"] == 0.03
    assert learning["learning_samples"] == 4
    assert learning["diagnosis"] == "Valid learning session"
    opened = recorder._build_record(_data(True), _store(), now + timedelta(minutes=1), "state_change", [])
    assert opened["window_events"][0]["event"] == "ventilation_opened"
    closed = recorder._build_record(_data(False), _store(), now + timedelta(minutes=6), "state_change", [])
    assert closed["window_events"][0]["event"] == "ventilation_closed"
    assert closed["window_events"][0]["duration_seconds"] == 300.0


def test_cleanup_keeps_30_day_window(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.0")
    recorder.directory.mkdir(parents=True)
    now = datetime(2026, 9, 30, 12, 0)
    keep = recorder.directory / "2026-09-01.jsonl"
    old = recorder.directory / "2026-08-31.jsonl"
    keep.write_text("{}\n")
    old.write_text("{}\n")
    recorder._cleanup_files(now)
    assert keep.exists()
    assert not old.exists()


def test_export_builds_beta_test_dossier(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    recorder.update_configuration_snapshot(
        {"levels": ["EG"], "rooms": [{"key": "living", "name": "Wohnzimmer", "volume": 75}]},
        {"start_rh": 62.0, "heating_system": "gas"}, _data(), now,
    )
    recorder.directory.mkdir(parents=True)
    record = recorder._build_record(
        _data(False), _store(), now, "session_completed",
        [{"name": "Wohnzimmer", "recommendation_followed": True}],
    )
    import json
    (recorder.directory / "2026-09-10.jsonl").write_text(json.dumps(record) + "\n")
    exported = recorder._export_sync(now + timedelta(hours=1))
    dossier = exported["test_dossier"]
    assert exported["retention_days"] == 30
    assert dossier["record_count"] == 1
    assert dossier["completed_session_count"] == 1
    assert dossier["recommendation_followed_session_count"] == 1
    assert dossier["configuration"]["freshairiq_version"] == "0.18.2.0"

def test_async_record_writes_and_exports_portable_file(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    recorder.update_configuration_snapshot(
        {"levels": ["EG"], "rooms": [{"key": "living", "name": "Wohnzimmer", "volume": 75}]},
        {"start_rh": 62.0, "heating_system": "gas"}, _data(), now,
    )
    wrote = asyncio.run(recorder.async_record(_data(False), _store(), now, []))
    assert wrote is True
    chunk = recorder.directory / "2026-09-10.jsonl"
    assert chunk.exists()
    exported = asyncio.run(recorder.async_export())
    assert exported["record_count"] == 1
    assert exported["records"][0]["freshairiq_version"] == "0.18.2.0"
    assert exported["records"][0]["configuration_snapshot"]["rooms"][0]["name"] == "Wohnzimmer"


def test_export_respects_payload_byte_limit(tmp_path: Path, monkeypatch):
    import json
    import custom_components.freshairiq.diagnostics as diagnostics

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.2")
    recorder.directory.mkdir(parents=True)
    rows = [recorder._build_record(_data(False), _store(), datetime(2026, 9, 10, 12, i), "periodic", []) for i in range(5)]
    path = recorder.directory / "2026-09-10.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    first_line_bytes = len((json.dumps(rows[0]) + "\n").encode("utf-8"))
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_MAX_EXPORT_BYTES", first_line_bytes + 10)
    exported = recorder._export_sync(datetime(2026, 9, 10, 13, 0))
    assert exported["truncated"] is True
    assert exported["record_count"] == 1
    assert exported["export_payload_bytes"] <= diagnostics.DIAGNOSTICS_MAX_EXPORT_BYTES


def test_capped_export_prefers_newest_records(tmp_path: Path, monkeypatch):
    import json
    import custom_components.freshairiq.diagnostics as diagnostics

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.18.2.2")
    recorder.directory.mkdir(parents=True)
    old = recorder._build_record(_data(False), _store(), datetime(2026, 9, 9, 12, 0), "periodic", [])
    new = recorder._build_record(_data(False), _store(), datetime(2026, 9, 10, 12, 0), "periodic", [])
    old_line = json.dumps(old) + "\n"
    new_line = json.dumps(new) + "\n"
    (recorder.directory / "2026-09-09.jsonl").write_text(old_line, encoding="utf-8")
    (recorder.directory / "2026-09-10.jsonl").write_text(new_line, encoding="utf-8")
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_MAX_EXPORT_BYTES", len(new_line.encode("utf-8")) + 10)
    exported = recorder._export_sync(datetime(2026, 9, 10, 13, 0))
    assert exported["truncated"] is True
    assert exported["record_count"] == 1
    assert exported["records"][0]["timestamp"].startswith("2026-09-10")


def test_idle_sampling_is_compact_and_15_minutes(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.20.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    assert asyncio.run(recorder.async_record(_data(False), _store(), now, [])) is True
    # Same state inside the idle cadence must not create a duplicate record.
    assert asyncio.run(recorder.async_record(_data(False), _store(), now + timedelta(minutes=14), [])) is False
    assert asyncio.run(recorder.async_record(_data(False), _store(), now + timedelta(minutes=15), [])) is True
    lines = (recorder.directory / "2026-09-10.jsonl").read_text(encoding="utf-8").splitlines()
    import json
    second = json.loads(lines[-1])
    assert second["record_type"] == "trend"
    assert second["reason"] == "idle_sample"
    assert "configuration_snapshot" not in second
    assert "decision_intelligence" not in second


def test_active_ventilation_keeps_two_minute_sampling(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.20.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    # Prime the state as active. The first row is a full state-change event.
    assert asyncio.run(recorder.async_record(_data(True), _store(), now, [])) is True
    assert asyncio.run(recorder.async_record(_data(True), _store(), now + timedelta(seconds=119), [])) is False
    assert asyncio.run(recorder.async_record(_data(True), _store(), now + timedelta(seconds=120), [])) is True
    import json
    lines = (recorder.directory / "2026-09-10.jsonl").read_text(encoding="utf-8").splitlines()
    sample = json.loads(lines[-1])
    assert sample["record_type"] == "trend"
    assert sample["reason"] == "active_sample"


def test_window_transition_is_recorded_immediately_and_full(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.20.2.0")
    now = datetime(2026, 9, 10, 12, 0)
    asyncio.run(recorder.async_record(_data(False), _store(), now, []))
    assert asyncio.run(recorder.async_record(_data(True), _store(), now + timedelta(seconds=5), [])) is True
    import json
    lines = (recorder.directory / "2026-09-10.jsonl").read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[-1])
    assert event["record_type"] == "event"
    assert event["reason"] == "window_event"
    assert event["window_events"][0]["event"] == "ventilation_opened"
    assert "configuration_snapshot" in event


def test_legacy_routine_rows_are_compacted_before_storage_cap(tmp_path: Path):
    import json
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.20.2.0")
    recorder.directory.mkdir(parents=True)
    now = datetime(2026, 9, 30, 12, 0)
    legacy = recorder._build_record(_data(False), _store(), datetime(2026, 9, 10, 12, 0), "periodic", [])
    legacy.pop("record_type", None)
    path = recorder.directory / "2026-09-10.jsonl"
    original = json.dumps(legacy, ensure_ascii=False) + "\n"
    path.write_text(original * 5, encoding="utf-8")
    before = path.stat().st_size
    recorder._cleanup_files(now)
    after = path.stat().st_size
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert after < before
    assert all(row["record_type"] == "trend_legacy_compacted" for row in rows)


def test_typical_30_day_trace_fits_export_budget(tmp_path: Path):
    """A 12-room typical trace should remain comfortably below 24 MiB."""
    import json
    import custom_components.freshairiq.diagnostics as diagnostics

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.20.2.0")
    data = _data(False)
    base = dict(
        data["rooms"]["living"],
        surface_rh=67.0, mould_level="low", co2=800, co2_available=True,
        action="Wait", potential_ml=220, realistic_potential_ml=180, result_ml=0,
        forecast_moisture_effect_ml=-80, forecast_temperature_change_c=-0.2,
        moisture_effect_next_5_min_ml=-40, temp_next_5_min_c=-0.1,
    )
    data["rooms"] = {
        f"room_{idx}": dict(base, key=f"room_{idx}", name=f"Raum {idx}")
        for idx in range(12)
    }
    row = recorder._build_trend_record(data, datetime(2026, 9, 10, 12, 0), "idle_sample")
    line_bytes = len((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    # Typical assumption: 22 h idle at 15-minute cadence + 2 h active at 2-minute cadence.
    samples_per_day = (22 * 4) + (2 * 30)
    projected = line_bytes * samples_per_day * 30
    assert projected < diagnostics.DIAGNOSTICS_MAX_EXPORT_BYTES


def test_json_safe_rejects_nonfinite_numbers():
    import json
    from custom_components.freshairiq.diagnostics import _json_safe

    safe = _json_safe({"nan": float("nan"), "inf": float("inf"), "ninf": float("-inf"), "ok": 1.25})
    assert safe == {"nan": None, "inf": None, "ninf": None, "ok": 1.25}
    # strict JSON must succeed; allow_nan=False would otherwise reject NaN/Infinity.
    json.dumps(safe, allow_nan=False)


def test_diagnostic_record_with_nonfinite_values_exports_strict_json(tmp_path: Path):
    import json
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    data = _data(False)
    data["forecast_cost"] = float("nan")
    data["rooms"]["living"]["humidity"] = float("inf")
    record = recorder._build_record(data, _store(), datetime(2026, 9, 14, 6, 0), "periodic", [])
    json.dumps(record, allow_nan=False)
    assert record["house"]["forecast_cost"] is None


def test_export_reports_corrupt_json_line_without_aborting(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    path = recorder.directory / "2026-09-14.jsonl"
    path.write_text('{"timestamp":"2026-09-14T05:00:00"}\n{broken-json}\n', encoding="utf-8")
    exported = recorder._export_sync(datetime(2026, 9, 14, 7, 0))
    assert exported["record_count"] == 1
    assert exported["read_errors"] == ["2026-09-14.jsonl:2"]


def test_cleanup_ignores_non_date_jsonl_filename(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    odd = recorder.directory / "manual-backup.jsonl"
    odd.write_text("{}\n", encoding="utf-8")
    recorder._cleanup_files(datetime(2026, 9, 14, 7, 0))
    assert odd.exists()


def test_diagnostics_tolerates_corrupt_room_maps_and_learning_counters(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    data = _data(False)
    data["rooms"] = {"living": data["rooms"]["living"], "broken": "not-a-room"}
    store = _store()
    store["rooms"]["broken"] = "not-a-room"
    store["night_model_samples"] = "nan"
    store["house_strategy_samples"] = float("inf")
    store["house_strategy_successes"] = "broken"

    record = recorder._build_record(data, store, datetime(2026, 9, 14, 8, 0), "state_change", [])
    assert len(record["rooms"]) == 1
    assert len(record["learning"]["rooms"]) == 1
    assert record["learning"]["night_model_samples"] == 0
    assert record["learning"]["house_strategy_samples"] == 0
    assert record["learning"]["house_strategy_successes"] == 0


def test_diagnostics_signature_and_activity_ignore_corrupt_room_container(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    assert recorder._is_active_ventilation({"rooms": ["bad"]}) is False
    signature = recorder._signature({"rooms": {"broken": "bad"}, "status": "ok"})
    assert isinstance(signature, str)
    assert '"active": []' in signature


def test_window_events_ignore_corrupt_room_rows(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    now = datetime(2026, 9, 14, 8, 0)
    assert recorder._window_events({"rooms": {"broken": "bad"}}, now) == []


def test_export_skips_valid_json_that_is_not_an_object(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    path = recorder.directory / "2026-09-14.jsonl"
    path.write_text('[1,2,3]\n{"timestamp":"2026-09-14T05:00:00"}\n', encoding="utf-8")
    exported = recorder._export_sync(datetime(2026, 9, 14, 7, 0))
    assert exported["record_count"] == 1
    assert exported["read_errors"] == ["2026-09-14.jsonl:1:non_object"]


def test_export_tolerates_corrupt_session_event_and_quality_shapes(tmp_path: Path):
    import json
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    record = {
        "timestamp": "2026-09-14T05:00:00",
        "reason": "state_change",
        "completed_sessions": {"bad": True},
        "window_events": "bad",
        "sensor_quality": {"room_quality_percent": float("nan")},
    }
    # JSON text uses null instead of NaN to remain standards-compliant; a second
    # record exercises a non-dict sensor-quality payload.
    record["sensor_quality"]["room_quality_percent"] = None
    record2 = dict(record, timestamp="2026-09-14T06:00:00", sensor_quality="bad")
    path = recorder.directory / "2026-09-14.jsonl"
    path.write_text(json.dumps(record) + "\n" + json.dumps(record2) + "\n", encoding="utf-8")
    exported = recorder._export_sync(datetime(2026, 9, 14, 7, 0))
    dossier = exported["test_dossier"]
    assert dossier["completed_session_count"] == 0
    assert dossier["window_event_count"] == 0
    assert dossier["average_room_data_quality_percent"] is None


def test_diagnostic_status_reports_runtime_state(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder._last_recorded_at = datetime(2026, 9, 14, 7, 0)
    recorder.record_count_session = 3
    recorder.last_error = "disk"
    status = recorder.status
    assert status["records_this_runtime"] == 3
    assert status["last_error"] == "disk"
    assert status["last_recorded_at"].startswith("2026-09-14T07:00:00")


def test_configuration_snapshot_ignores_corrupt_room_containers(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    now = datetime(2026, 9, 14, 8, 0)
    recorder.update_configuration_snapshot({"rooms": "bad"}, {}, {"rooms": "bad"}, now)
    assert recorder._config_snapshot["rooms"] == []

    recorder.update_configuration_snapshot(
        {"rooms": ["bad", {"key": "living", "name": "Living", "contacts": []}]},
        {}, {"rooms": {"living": {"name": "Living"}}}, now,
    )
    assert [room["key"] for room in recorder._config_snapshot["rooms"]] == ["living"]


def test_build_record_filters_corrupt_completed_sessions_and_window_events(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    record = recorder._build_record(
        _data(False), _store(), datetime(2026, 9, 14, 8, 0), "state_change",
        [{"recommendation_followed": True}, "bad"],
        window_events=[{"event": "ok"}, "bad"],
    )
    assert record["recommendation_tracking"]["completed_session_count"] == 1
    assert record["recommendation_tracking"]["followed_session_count"] == 1
    assert record["completed_sessions"] == [{"recommendation_followed": True}]
    assert record["window_events"] == [{"event": "ok"}]


def test_monitor_only_room_is_not_counted_as_sensor_quality_problem(tmp_path: Path):
    """A deliberately excluded room must stay visible without degrading quality."""
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.47")
    data = _data(False)
    data["rooms"]["wintergarten"] = {
        "key": "wintergarten",
        "name": "Wintergarten",
        "floor": "Wintergarten",
        "volume_m3": 29.7,
        "calculation_enabled": False,
        "monitor_only": True,
        "data_quality": "monitor_only",
        "active": False,
        "temperature": 16.2,
        "humidity": 59.8,
        "absolute_humidity": 8.24,
    }

    record = recorder._build_record(data, _store(), datetime(2026, 9, 22, 4, 0), "periodic", [])
    quality = record["sensor_quality"]

    assert quality["rooms_all_total"] == 2
    assert quality["rooms_monitor_only"] == 1
    assert quality["rooms_total"] == 1
    assert quality["rooms_ok"] == 1
    assert quality["rooms_with_issues"] == 0
    assert quality["room_quality_percent"] == 100.0
    assert quality["issues"] == []
    # The monitor-only room must still be exported for diagnostics/visibility.
    wintergarten = next(room for room in record["rooms"] if room["key"] == "wintergarten")
    assert wintergarten["data_quality"] == "monitor_only"
    assert wintergarten["calculation_enabled"] is False


def test_calculation_active_bad_room_still_counts_as_sensor_quality_problem(tmp_path: Path):
    """The monitor-only fix must not hide genuine calculation-room failures."""
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.47")
    data = _data(False, quality="missing_humidity")
    data["rooms"]["living"]["calculation_enabled"] = True

    record = recorder._build_record(data, _store(), datetime(2026, 9, 22, 4, 1), "periodic", [])
    quality = record["sensor_quality"]

    assert quality["rooms_total"] == 1
    assert quality["rooms_monitor_only"] == 0
    assert quality["rooms_with_issues"] == 1
    assert quality["room_quality_percent"] == 0.0
    assert quality["issues"][0]["room_key"] == "living"
