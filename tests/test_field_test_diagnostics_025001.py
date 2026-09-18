"""Field-test evidence hardening for FreshAirIQ v0.25.0.7."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

# Reuse the established standalone Home Assistant stubs and test helpers.
from test_diagnostics import FreshAirIQDiagnosticsRecorder, _Hass, _data, _store


def test_field_test_identity_is_stable_and_export_sequence_increments(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry-secret", "0.25.0.7")
    now = datetime(2026, 9, 15, 14, 0)
    first = recorder._export_sync(now, {"home_assistant_version": "2026.9.1", "installation_type": "Home Assistant OS"})
    second = recorder._export_sync(now + timedelta(minutes=5), {"home_assistant_version": "2026.9.1", "installation_type": "Home Assistant OS"})

    first_field = first["field_test"]
    second_field = second["field_test"]
    assert first_field["anonymous_installation_id"].startswith("faiq-install-")
    assert second_field["anonymous_installation_id"] == first_field["anonymous_installation_id"]
    assert first_field["config_entry_fingerprint"] == second_field["config_entry_fingerprint"]
    assert second_field["export_sequence"] == first_field["export_sequence"] + 1
    assert first_field["export_id"] != second_field["export_id"]
    assert first_field["runtime_environment"]["home_assistant_version"] == "2026.9.1"


def test_field_test_client_registry_is_anonymous_and_persistent(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    now = datetime(2026, 9, 15, 14, 0)
    context = {
        "client_id": "faiq-client-abc123def456",
        "client_id_persistence": "localStorage",
        "platform_family": "Android",
        "os_version": "16",
        "device_class": "phone",
        "device_family": "Android phone",
        "device_model": "SM-S938B",
        "companion_app": True,
        "companion_app_version": "2026.9.0",
        "browser_family": "Home Assistant WebView",
        "browser_version": "140.0",
        "webview_engine_version": "140.0",
        "home_assistant_version_reported_by_frontend": "2026.9.1",
        "freshairiq_frontend_version": "0.25.0.7",
        "viewport_css_px": {"width": 412, "height": 915},
        "screen_css_px": {"width": 412, "height": 915},
        "device_pixel_ratio": 2.625,
        "touch_points": 5,
        "standalone_display_mode": False,
        # Deliberately hostile extra fields: the whitelist must drop them.
        "user_agent": "MUST NEVER BE STORED",
        "device_name": "Pauls Telefon",
    }
    result = recorder._register_client_sync(context, now)
    assert result == {"registered": True, "client_id": "faiq-client-abc123def456"}

    exported = recorder._export_sync(now + timedelta(minutes=1))
    clients = exported["field_test"]["known_clients"]
    assert len(clients) == 1
    assert clients[0]["current"]["device_model"] == "SM-S938B"
    assert clients[0]["current"]["platform_family"] == "Android"
    text = json.dumps(exported, ensure_ascii=False)
    assert "MUST NEVER BE STORED" not in text
    assert "Pauls Telefon" not in text
    assert '"user_agent":' not in text
    assert '"device_name":' not in text
    assert recorder._register_client_sync({"client_id": "faiq-client-Paul Example"}, now)["registered"] is False


def test_field_test_export_proves_observation_continuity_and_versions(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    for day, version, ha_version in [
        (10, "0.25.0.0", "2026.9.0"),
        (11, "0.25.0.0", "2026.9.0"),
        (12, "0.25.0.7", "2026.9.1"),
    ]:
        stamp = datetime(2026, 9, day, 12, 0)
        row = recorder._build_record(_data(False), _store(), stamp, "periodic", [])
        row["freshairiq_version"] = version
        row["runtime_environment"] = {"home_assistant_version": ha_version}
        (recorder.directory / f"2026-09-{day:02d}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    exported = recorder._export_sync(datetime(2026, 9, 12, 13, 0))
    field = exported["field_test"]
    observation = field["observation"]
    assert observation["calendar_days_with_records"] == 3
    assert observation["longest_consecutive_calendar_day_streak"] == 3
    assert observation["period_span_days"] == 2.0
    assert observation["record_count"] == 3
    assert {row["version"] for row in field["freshairiq_version_history"]} == {"0.25.0.0", "0.25.0.7"}
    assert {row["version"] for row in field["home_assistant_version_history"]} == {"2026.9.0", "2026.9.1"}
    assert len(field["data_integrity"]["records_sha256"]) == 64


def test_configuration_snapshot_exports_all_safe_defaults_but_not_sensitive_identity_values(tmp_path: Path):
    from custom_components.freshairiq.const import DEFAULT_OPTIONS
    from custom_components.freshairiq.diagnostics import _SAFE_OPTION_KEYS

    sensitive = {
        "adult_presence_entities",
        "child_presence_entities",
        "adult_resident_names",
        "child_resident_names",
        "resident_room_profiles",
        "presence_sensor_entities",
        "pet_safe_presence_entities",
        "notification_targets",
    }
    assert set(DEFAULT_OPTIONS) - sensitive == set(_SAFE_OPTION_KEYS)

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    options = dict(DEFAULT_OPTIONS)
    options.update({
        "adult_presence_entities": ["person.private"],
        "adult_resident_names": "Private Name",
        "resident_room_profiles": '{"adult:0":{"room_keys":["living"]}}',
        "notification_targets": ["notify.private"],
    })
    recorder.update_configuration_snapshot(
        {"levels": ["EG"], "rooms": [{"key": "living", "name": "Wohnzimmer", "volume": 75}]},
        options,
        _data(),
        datetime(2026, 9, 15, 14, 0),
    )
    model_options = recorder._config_snapshot["model_options"]
    assert set(model_options) == set(_SAFE_OPTION_KEYS)
    text = json.dumps(recorder._config_snapshot, ensure_ascii=False)
    assert "person.private" not in text
    assert "Private Name" not in text
    assert "notify.private" not in text


def test_mixed_timezone_timestamp_history_does_not_break_field_test_export(tmp_path: Path):
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    recorder.directory.mkdir(parents=True)
    rows = [
        {"timestamp": "2026-09-15T10:00:00+02:00", "freshairiq_version": "0.25.0.7", "reason": "periodic"},
        {"timestamp": "2026-09-15T10:15:00", "freshairiq_version": "0.25.0.7", "reason": "periodic"},
    ]
    (recorder.directory / "2026-09-15.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    exported = recorder._export_sync(datetime(2026, 9, 15, 11, 0))
    assert exported["field_test"]["observation"]["largest_sampling_gap_minutes"] == 15.0


def test_routine_trend_records_keep_home_assistant_version_for_upgrade_history(tmp_path: Path, monkeypatch):
    import custom_components.freshairiq.diagnostics as diagnostics

    monkeypatch.setattr(diagnostics, "_runtime_environment_snapshot", lambda: {"home_assistant_version": "2026.9.1"})
    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    row = recorder._build_trend_record(_data(False), datetime(2026, 9, 15, 14, 0), "idle_sample")
    assert row["runtime_environment"] == {"home_assistant_version": "2026.9.1"}


def test_concurrent_exports_keep_identity_file_valid_and_sequences_unique(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    recorder = FreshAirIQDiagnosticsRecorder(_Hass(tmp_path), "entry", "0.25.0.7")
    now = datetime(2026, 9, 15, 14, 0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        exports = list(pool.map(lambda minute: recorder._export_sync(now + timedelta(minutes=minute)), (0, 1)))

    ids = {item["field_test"]["anonymous_installation_id"] for item in exports}
    sequences = {item["field_test"]["export_sequence"] for item in exports}
    assert len(ids) == 1
    assert sequences == {1, 2}
    identity = json.loads(recorder._identity_path.read_text(encoding="utf-8"))
    assert identity["export_sequence"] == 2
