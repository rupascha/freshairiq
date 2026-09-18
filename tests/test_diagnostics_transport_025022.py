"""Privacy, cadence and minimisation contracts for v0.25.0.35 diagnostics transport."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from custom_components.freshairiq.diagnostic_transport import (
    CURSOR_SCHEMA_VERSION,
    DEFAULT_MAX_UPLOAD_RECORDS,
    REPORTING_MODES,
    UPLOAD_SCHEMA_VERSION,
    _canonical_json_bytes,
    _collect_room_keys,
    _record_transport_id,
    _redact_text,
    _safe_client_context,
    _safe_configuration,
    _sanitize_analysis_tree,
    _sanitize_tree,
    build_analysis_export,
    build_cloud_payload,
    build_upload_chunks,
    deterministic_upload_slot,
    normalise_reporting_mode,
    problem_fingerprint,
    record_cursor,
    retry_delay_seconds,
    room_token,
    select_records_after_cursor,
    upload_due,
)


def _export() -> dict:
    return {
        "format": "FreshAirIQ diagnostic export",
        "schema_version": 10,
        "freshairiq_version": "0.25.0.35",
        "exported_at": "2026-09-16T23:00:00+02:00",
        "field_test": {
            "anonymous_installation_id": "faiq-install-abc123def456",
            "config_entry_fingerprint": "secret-fingerprint",
            "identity_created_at": "2026-09-01T00:00:00+02:00",
            "runtime_environment": {
                "home_assistant_version": "2026.9.2",
                "installation_type": "Home Assistant OS",
                "channel": "stable",
                "dev": False,
                "hassio": True,
                "docker": True,
                "virtualenv": False,
                "python_version": "3.14.6",
                "os_name": "Linux",
                "os_version": "6.12",
                "architecture": "aarch64",
                "container_architecture": "aarch64",
                "timezone": "Europe/Berlin",
            },
            "observation": {
                "period_start": "2026-09-15T00:00:00+02:00",
                "period_end": "2026-09-16T23:00:00+02:00",
                "period_span_days": 1.958,
                "calendar_days_with_records": 2,
                "recorded_calendar_days": ["2026-09-15", "2026-09-16"],
                "longest_consecutive_calendar_day_streak": 2,
                "largest_sampling_gap_minutes": 15.0,
                "sampling_gaps_over_30_minutes": 0,
                "record_count": 2,
                "truncated": False,
                "read_error_count": 0,
            },
            "freshairiq_version_history": [{"version": "0.25.0.35", "record_count": 2}],
            "home_assistant_version_history": [{"version": "2026.9.2", "record_count": 2}],
            "known_clients": [
                {
                    "client_id": "faiq-client-abc123def456",
                    "current": {
                        "platform_family": "iOS",
                        "device_class": "phone",
                        "device_model": "iPhone15,3",
                        "device_family": "Paul's phone",
                        "companion_app": True,
                        "companion_app_version": "2026.9.1",
                        "browser_family": "Home Assistant WebView",
                        "browser_version": "18.6",
                        "webview_engine_version": "18.6",
                        "viewport_css_px": {"width": 429, "height": 930},
                        "device_pixel_ratio": 3.0,
                    },
                }
            ],
            "export_client": {"device_model": "iPhone15,3"},
        },
        "test_dossier": {
            "period_start": "2026-09-15T00:00:00+02:00",
            "period_end": "2026-09-16T23:00:00+02:00",
            "period_span_days": 1.958,
            "calendar_days_with_records": 2,
            "longest_consecutive_calendar_day_streak": 2,
            "largest_sampling_gap_minutes": 15.0,
            "record_count": 2,
            "reason_counts": {"periodic": 1, "session_completed": 1},
            "completed_session_count": 1,
            "recommendation_followed_session_count": 1,
            "window_event_count": 2,
            "average_room_data_quality_percent": 98.5,
            "configuration": {
                "freshairiq_version": "0.25.0.35",
                "diagnostics_schema_version": 10,
                "levels": ["EG Paul"],
                "model_options": {
                    "start_rh": 62.0,
                    "threshold_mode": "adaptive_home_size",
                    "adult_occupants": 2,
                    "child_occupants": 2,
                    "electricity_price_per_kwh": 0.31,
                    "notification_scope": "house",
                    "statistics_days": 14,
                    "diagnostics_reporting_mode": "daily",
                },
                "capabilities": {
                    "weather_entity_configured": True,
                    "adult_presence_tracker_count": 2,
                    "notification_target_count": 2,
                },
                "rooms": [
                    {
                        "key": "fiona_room",
                        "name": "Fionas Zimmer",
                        "floor": "ground_floor",
                        "volume_m3": 32.0,
                        "contact_count": 1,
                        "temperature_sensor_configured": True,
                        "humidity_sensor_configured": True,
                    },
                    {
                        "key": "living",
                        "name": "Wohnküche Paul",
                        "floor": "EG Paul",
                        "volume_m3": 85.0,
                        "contact_count": 3,
                    },
                    "corrupt-room-row",
                ],
            },
            "forecast_validation": {
                "room_results": [
                    {"room_key": "fiona_room", "room_name": "Fionas Zimmer", "actual_removed_ml": 22.0}
                ]
            },
            "forecast_backtest": {"rooms": {"living": {"room_key": "living", "mae_ml": 12.0}}},
        },
        "records": [
            {
                "timestamp": "2026-09-16T22:00:00+02:00",
                "rooms": [
                    {
                        "key": "fiona_room",
                        "name": "Fionas Zimmer",
                        "temperature": 21.0,
                        "entity_hint": "sensor.fiona_private",
                    }
                ],
                "decision": {"room_keys": ["fiona_room"], "text": "fiona_room sensor.fiona_private"},
                "window_events": [{"room_key": "fiona_room", "room_name": "Fionas Zimmer"}],
                "debug": "Fionas Zimmer mail paul@example.com ip 192.168.1.5 https://private.local/path",
            },
            {
                "timestamp": "2026-09-16T23:00:00+02:00",
                "rooms": [{"key": "living", "name": "Wohnküche Paul", "temperature": 22.0}],
                "decision": {"room_keys": ["living"]},
            },
        ],
    }


def test_constants_and_mode_normalisation_fail_closed():
    assert UPLOAD_SCHEMA_VERSION == 2
    assert CURSOR_SCHEMA_VERSION == 1
    assert REPORTING_MODES == ("off", "errors", "daily", "weekly")
    assert DEFAULT_MAX_UPLOAD_RECORDS == 240
    assert normalise_reporting_mode(None) == "off"
    assert normalise_reporting_mode(" DAILY ") == "daily"
    assert normalise_reporting_mode("bogus") == "off"


def test_deterministic_slot_is_stable_and_inside_two_hour_window():
    first = deterministic_upload_slot("faiq-install-one")
    second = deterministic_upload_slot("faiq-install-one")
    other = deterministic_upload_slot("faiq-install-two")
    assert first == second
    assert first != other
    assert first[0] in {2, 3}
    assert 0 <= first[1] <= 59
    assert deterministic_upload_slot("")[0] in {2, 3}


def test_daily_weekly_error_and_off_cadence():
    install = "faiq-install-abc123"
    hour, minute = deterministic_upload_slot(install)
    now = datetime(2026, 9, 16, hour, minute, tzinfo=timezone.utc)
    assert upload_due("off", now, install) is False
    assert upload_due("daily", now - timedelta(minutes=1), install) is False
    assert upload_due("daily", now, install) is True
    assert upload_due("daily", now + timedelta(minutes=1), install, last_success_at=now.isoformat()) is False
    assert upload_due("daily", now + timedelta(days=1), install, last_success_at=now.isoformat()) is True
    # Naive persisted timestamps are accepted when now is timezone-aware.
    assert upload_due("daily", now + timedelta(days=1), install, last_success_at=now.replace(tzinfo=None).isoformat()) is True
    naive_now = now.replace(tzinfo=None) + timedelta(days=1)
    assert upload_due("daily", naive_now, install, last_success_at=now.isoformat()) is True

    # Compute this installation's stable weekly target and test both sides.
    import hashlib
    weekday = hashlib.sha256(install.encode()).digest()[2] % 7
    monday = datetime(2026, 9, 14, tzinfo=timezone.utc)
    weekly_target = monday + timedelta(days=weekday, hours=hour, minutes=minute)
    assert upload_due("weekly", weekly_target - timedelta(minutes=1), install) is False
    assert upload_due("weekly", weekly_target, install) is True
    assert upload_due("weekly", weekly_target + timedelta(minutes=1), install, last_success_at=weekly_target.isoformat()) is False
    assert upload_due("weekly", weekly_target + timedelta(days=7), install, last_success_at=weekly_target.isoformat()) is True

    assert upload_due("errors", now, install) is False
    assert upload_due("errors", now, install, problem_fingerprint="a", last_problem_fingerprint="b") is True
    assert upload_due("errors", now, install, problem_fingerprint="a", last_problem_fingerprint="a") is True
    assert upload_due("errors", now, install, last_success_at=now.isoformat(), problem_fingerprint="a", last_problem_fingerprint="a") is False
    assert upload_due("errors", now + timedelta(hours=24), install, last_success_at=now.isoformat(), problem_fingerprint="a", last_problem_fingerprint="a") is True
    # Broken timestamps must not make the scheduler crash.
    assert upload_due("errors", now, install, last_success_at="not-a-date", problem_fingerprint="a", last_problem_fingerprint="a") is True


def test_retry_backoff_is_bounded_and_defensive():
    assert retry_delay_seconds(1) == 300
    assert retry_delay_seconds(2) == 600
    assert retry_delay_seconds(99) == 21600
    assert retry_delay_seconds("bad") == 300
    assert retry_delay_seconds(0) == 300


def test_problem_fingerprint_only_uses_coarse_health_signals():
    assert problem_fingerprint(None) is None
    assert problem_fingerprint({}) is None
    assert problem_fingerprint({"robustness": {"consecutive_failures": "bad"}}) is None
    one = problem_fingerprint({
        "robustness": {
            "consecutive_failures": 2,
            "last_failure_type": "UpdateFailed",
            "runtime_config_issues": ["missing_humidity", "missing_temperature"],
        },
        "diagnostics": {"last_error": "OSError: /private/path"},
    })
    two = problem_fingerprint({
        "robustness": {
            "consecutive_failures": 2,
            "last_failure_type": "UpdateFailed",
            "runtime_config_issues": ["missing_temperature", "missing_humidity"],
        },
        "diagnostics": {"last_error": "OSError: another secret path"},
    })
    assert one == two
    assert one and len(one) == 64
    issue_only = problem_fingerprint({"robustness": {"runtime_config_issues": ["x"]}})
    error_only = problem_fingerprint({"diagnostics": {"last_error": "ValueError: secret"}})
    assert issue_only and error_only and issue_only != error_only
    capped = problem_fingerprint({"robustness": {"consecutive_failures": 50000}})
    assert capped


def test_room_tokens_are_stable_per_installation():
    a = room_token("living", "install-a")
    assert a == room_token("living", "install-a")
    assert a != room_token("living", "install-b")
    assert a.startswith("room-") and len(a) == 17


def test_tree_helpers_collect_pseudonymise_and_redact():
    source = {
        "room_key": "living",
        "room_keys": ["bed", "living"],
        "followed_room_keys": ["bath"],
        "rooms": {"office": {"temperature": 21}},
        "nested": {"rooms": [{"key": "kid"}, {"key": 123}]},
        "tuple": ({"room_key": "guest"},),
    }
    found = _collect_room_keys(source)
    assert found == {"living", "bed", "bath", "office", "kid", "guest"}
    assert _collect_room_keys("not-a-container", found) is found

    room_map = {key: f"r-{index:03d}" for index, key in enumerate(sorted(found), 1)}
    text = _redact_text(
        "living sensor.private paul@example.com 192.168.0.1 https://example.com/x",
        room_map,
    )
    assert "living" not in text
    assert "sensor.private" not in text
    assert "paul@example.com" not in text
    assert "192.168.0.1" not in text
    assert "https://example.com/x" not in text
    clean = _sanitize_tree(
        {"name": "Private", "living": {"value": "living"}, "tuple": ("bed", 1), "obj": object()},
        room_map,
    )
    assert "name" not in clean
    assert room_map["living"] in clean
    assert clean[room_map["living"]]["value"] == room_map["living"]
    assert clean["tuple"] == [room_map["bed"], 1]
    assert isinstance(clean["obj"], str)


def test_configuration_and_client_context_helpers_minimise_data():
    export = _export()
    config = export["test_dossier"]["configuration"]
    install = export["field_test"]["anonymous_installation_id"]
    room_map = {
        "fiona_room": room_token("fiona_room", install),
        "living": room_token("living", install),
    }
    safe = _safe_configuration(config, room_map)
    assert safe["model_options"]["start_rh"] == 62.0
    assert "adult_occupants" not in safe["model_options"]
    assert "electricity_price_per_kwh" not in safe["model_options"]
    assert "notification_scope" not in safe["model_options"]
    assert "levels" not in safe
    assert safe["rooms"][1]["floor"] == "custom"
    assert "Fionas Zimmer" not in json.dumps(safe, ensure_ascii=False)
    assert _safe_configuration(None, room_map) == {}

    clients = _safe_client_context(export["field_test"])
    assert clients[0]["platform_family"] == "iOS"
    assert "device_model" not in clients[0]
    assert "device_family" not in clients[0]
    assert _safe_client_context({}) == []
    assert _safe_client_context({"known_clients": ["bad", {"current": "bad"}]}) == [
        {
            "platform_family": None,
            "device_class": None,
            "companion_app": False,
            "companion_app_version": None,
            "browser_family": None,
            "browser_version": None,
            "webview_engine_version": None,
            "viewport_css_px": None,
            "device_pixel_ratio": None,
        }
    ]


def test_cloud_payload_removes_identifiers_and_is_deterministic_for_same_export():
    source = _export()
    payload = build_cloud_payload(source, max_records=1)
    assert payload["upload_schema_version"] == 2
    assert payload["anonymous_installation_id"] == "faiq-install-abc123def456"
    assert payload["runtime_environment"]["home_assistant_version"] == "2026.9.2"
    assert "timezone" not in payload["runtime_environment"]
    assert payload["privacy"]["client_context_included"] is False
    assert "client_context" not in payload
    assert len(payload["records"]) == 1
    text = json.dumps(payload, ensure_ascii=False)
    for secret in (
        "Fionas Zimmer",
        "Wohnküche Paul",
        "fiona_room",
        '"living"',
        "sensor.fiona_private",
        "paul@example.com",
        "192.168.1.5",
        "https://private.local/path",
        "iPhone15,3",
        "Paul's phone",
        "secret-fingerprint",
        "Europe/Berlin",
        "EG Paul",
    ):
        assert secret not in text
    assert "adult_occupants" not in text
    assert "electricity_price_per_kwh" not in text
    assert len(payload["content_sha256"]) == 64

    with_context = build_cloud_payload(source, include_client_context=True, max_records=99)
    assert with_context["privacy"]["client_context_included"] is True
    assert with_context["client_context"][0]["platform_family"] == "iOS"
    context_text = json.dumps(with_context["client_context"], ensure_ascii=False)
    assert "iPhone15,3" not in context_text
    assert "Paul's phone" not in context_text

    no_records = build_cloud_payload(source, max_records=0)
    assert no_records["records"] == []
    fallback_limit = build_cloud_payload(source, max_records="bad")
    assert len(fallback_limit["records"]) == 2
    capped = build_cloud_payload(source, max_records=50000)
    assert len(capped["records"]) == 2


def test_cloud_payload_rejects_export_without_anonymous_identity():
    source = _export()
    source["field_test"]["anonymous_installation_id"] = None
    with pytest.raises(ValueError, match="anonymous installation id"):
        build_cloud_payload(source)
    with pytest.raises(ValueError):
        build_cloud_payload({})



def test_analysis_export_keeps_full_technical_dossier_but_redacts_private_labels():
    source = _export()
    source["test_dossier"]["configuration"]["adult_resident_names"] = ["Paul"]
    source["test_dossier"]["configuration"]["child_resident_names"] = ["Fiona"]
    source["field_test"]["extra_tuple"] = ("Paul", 1)
    source["field_test"]["extra_object"] = object()
    source["records"][0]["personalised_text"] = "Paul soll EG Paul prüfen"
    source_before = json.dumps(source, ensure_ascii=False, default=str, sort_keys=True)

    metadata, records = build_analysis_export(source, include_client_context=True)

    assert len(records) == 2
    assert metadata["transport"]["analysis_equivalent"] is True
    assert metadata["transport"]["full_retained_history"] is True
    assert metadata["test_dossier"]["configuration"]["model_options"]["adult_occupants"] == 2
    assert metadata["test_dossier"]["configuration"]["model_options"]["electricity_price_per_kwh"] == 0.31
    assert metadata["field_test"]["runtime_environment"]["home_assistant_version"] == "2026.9.2"
    assert "timezone" not in metadata["field_test"]["runtime_environment"]
    assert metadata["test_dossier"]["configuration"]["rooms"][1]["floor"] == "custom"
    assert metadata["client_context"][0]["platform_family"] == "iOS"
    assert "device_model" not in metadata["client_context"][0]
    assert metadata["field_test"]["extra_tuple"][0] == "<redacted_resident>"
    assert isinstance(metadata["field_test"]["extra_object"], str)

    text = json.dumps({"metadata": metadata, "records": records}, ensure_ascii=False)
    for secret in (
        "Fionas Zimmer",
        "Wohnküche Paul",
        "fiona_room",
        '"living"',
        "sensor.fiona_private",
        "paul@example.com",
        "192.168.1.5",
        "https://private.local/path",
        "iPhone15,3",
        "Paul's phone",
        "secret-fingerprint",
        "Europe/Berlin",
        "EG Paul",
    ):
        assert secret not in text
    assert "<redacted_resident>" in text
    assert "level-" in text
    # Transport preparation must not mutate the manual export object.
    assert json.dumps(source, ensure_ascii=False, default=str, sort_keys=True) == source_before

    no_context, _ = build_analysis_export(source, include_client_context=False)
    assert "client_context" not in no_context
    with pytest.raises(ValueError, match="anonymous installation id"):
        build_analysis_export({})
    with pytest.raises(ValueError, match="anonymous installation id"):
        build_analysis_export(None)  # type: ignore[arg-type]


def test_analysis_sanitizer_handles_container_and_scalar_shapes():
    room_map = {"private-room": "room-safe", "Private Room": "room-safe"}
    value = {
        "private-room": {"name": "Private Room", "floor": "My private floor"},
        "tuple": ("Private Room", 1),
        "list": [None, True, 1.5],
        "object": object(),
    }
    clean = _sanitize_analysis_tree(value, room_map)
    assert clean["room-safe"]["floor"] == "custom"
    assert clean["tuple"] == ["room-safe", 1]
    assert clean["list"] == [None, True, 1.5]
    assert isinstance(clean["object"], str)
    assert _canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_incremental_cursor_exact_match_and_retention_fallback_are_loss_safe():
    _, records = build_analysis_export(_export())
    first_cursor = record_cursor(records[0])
    assert first_cursor["schema_version"] == 1
    assert first_cursor["record_id"] == _record_transport_id(records[0])
    assert select_records_after_cursor(records, None) == records
    assert select_records_after_cursor(records, first_cursor) == [records[1]]

    # If the exact retained record disappeared, resend the timestamp boundary;
    # record IDs make this safe to deduplicate at the Hub.
    unknown_cursor = {
        "schema_version": 1,
        "timestamp": records[0]["timestamp"],
        "record_id": "not-retained-anymore",
    }
    fallback = select_records_after_cursor(records, unknown_cursor)
    assert fallback == records

    after_all = {
        "schema_version": 1,
        "timestamp": "2026-09-17T23:00:00+02:00",
        "record_id": "not-retained-anymore",
    }
    assert select_records_after_cursor(records, after_all) == []

    unknown_time_records = records + [{"value": 7}]
    assert unknown_time_records[-1] in select_records_after_cursor(unknown_time_records, after_all)


def test_v2_chunks_send_all_records_then_only_incremental_records_and_fit_limit():
    source = _export()
    source["records"] = []
    for index in range(18):
        source["records"].append({
            "timestamp": f"2026-09-16T{index:02d}:00:00+02:00",
            "rooms": [{"key": "living", "name": "Wohnküche Paul", "temperature": 20 + index / 10}],
            "blob": "x" * 900,
        })
    source["field_test"]["observation"]["record_count"] = len(source["records"])
    source["test_dossier"]["record_count"] = len(source["records"])

    limit = 9000
    chunks = build_upload_chunks(source, max_chunk_bytes=limit)
    assert len(chunks) > 1
    assert all(chunk["upload_schema_version"] == 2 for chunk in chunks)
    assert all(chunk["initial_snapshot"] is True for chunk in chunks)
    assert all(chunk["incremental"] is False for chunk in chunks)
    assert sum(len(chunk["records"]) for chunk in chunks) == 18
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert all(len(_canonical_json_bytes(chunk)) <= limit for chunk in chunks)
    assert all(len(chunk["record_ids"]) == len(chunk["records"]) for chunk in chunks)
    for chunk in chunks:
        assert all(len(record_id) == 64 for record_id in chunk["record_ids"])
    for left, right in zip(chunks, chunks[1:]):
        assert right["cursor_before"] == left["cursor_after"]

    first_cursor = chunks[0]["cursor_after"]
    remaining = build_upload_chunks(source, after_cursor=first_cursor, max_chunk_bytes=limit)
    assert all(chunk["initial_snapshot"] is False for chunk in remaining)
    assert all(chunk["incremental"] is True for chunk in remaining)
    assert sum(len(chunk["records"]) for chunk in remaining) < 18

    last_cursor = chunks[-1]["cursor_after"]
    metadata_only = build_upload_chunks(source, after_cursor=last_cursor, max_chunk_bytes=limit)
    assert len(metadata_only) == 1
    assert metadata_only[0]["records"] == []
    assert metadata_only[0]["record_ids"] == []
    assert metadata_only[0]["cursor_after"] == last_cursor
    assert metadata_only[0]["incremental"] is True

    # Invalid byte limits fail safely; malformed limits fall back to 2 MiB.
    assert build_upload_chunks(source, max_chunk_bytes="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="too small"):
        build_upload_chunks(source, max_chunk_bytes=1024)


def test_v2_chunk_builder_never_silently_trims_oversized_diagnostics():
    source = _export()
    source["records"] = [{
        "timestamp": "2026-09-16T23:00:00+02:00",
        "rooms": [{"key": "living", "name": "Wohnküche Paul"}],
        "blob": "x" * 12000,
    }]
    with pytest.raises(ValueError, match="one diagnostics record exceeds"):
        build_upload_chunks(source, max_chunk_bytes=7000)

    # Metadata-only snapshots also fail explicitly instead of dropping fields.
    source = _export()
    source["test_dossier"]["huge_analysis_field"] = "y" * 9000
    _, safe_records = build_analysis_export(source)
    cursor = record_cursor(safe_records[-1])
    with pytest.raises(ValueError, match="metadata exceeds"):
        build_upload_chunks(source, after_cursor=cursor, max_chunk_bytes=7000)


def test_v2_empty_history_still_sends_one_metadata_snapshot():
    source = _export()
    source["records"] = "corrupt-not-list"
    chunks = build_upload_chunks(source, max_chunk_bytes=2 * 1024 * 1024)
    assert len(chunks) == 1
    assert chunks[0]["records"] == []
    assert chunks[0]["initial_snapshot"] is True
