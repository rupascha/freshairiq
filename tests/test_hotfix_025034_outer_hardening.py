"""Regression contracts for v0.25.0.39 outer hardening hotfix."""
from __future__ import annotations

import json
from pathlib import Path

from custom_components.freshairiq.diagnostic_transport import (
    _version_literal_path,
    build_analysis_export,
    normalise_resident_names,
)
from custom_components.freshairiq.measurement_frame import last_valid_session_measurement, session_measurement_quality

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_missing_final_refresh_does_not_invalidate_last_numeric_session_state() -> None:
    snapshot = last_valid_session_measurement({
        "session_last_valid_temperature": 21.4,
        "session_last_valid_humidity": 55,
        "session_last_valid_reference_temperature": 8.2,
        "session_last_valid_reference_humidity": 72,
    })
    assert snapshot == {
        "temperature": 21.4,
        "humidity": 55.0,
        "reference_temperature": 8.2,
        "reference_humidity": 72.0,
    }


def test_invalid_or_missing_stored_end_snapshot_fails_closed() -> None:
    assert last_valid_session_measurement({}) is None
    assert last_valid_session_measurement({
        "session_last_valid_temperature": "unavailable",
        "session_last_valid_humidity": 55,
        "session_last_valid_reference_temperature": 8,
        "session_last_valid_reference_humidity": 70,
    }) is None




def test_missing_post_close_refresh_keeps_in_session_evidence_usable() -> None:
    quality = session_measurement_quality(
        2,
        temperature_reports=1,
        humidity_reports=1,
        final_temperature_feedback=False,
        final_humidity_feedback=False,
    )
    assert quality["timestamp_gate_passed"] is True
    assert quality["quality"] == "good"
    assert quality["learning_weight"] == 0.75


def test_last_valid_snapshot_rejects_non_mapping_and_non_finite_numbers() -> None:
    assert last_valid_session_measurement(None) is None
    assert last_valid_session_measurement({
        "session_last_valid_temperature": float("nan"),
        "session_last_valid_humidity": 55,
        "session_last_valid_reference_temperature": 8,
        "session_last_valid_reference_humidity": 70,
    }) is None


def test_resident_parser_is_bounded_and_empty_version_path_is_not_exempt() -> None:
    names = normalise_resident_names(",".join(f"Person {i}" for i in range(25)))
    assert len(names) == 20
    assert names[-1] == "Person 19"
    assert _version_literal_path(()) is False


def test_coordinator_timeout_has_fallback_and_deterministic_unmeasured_close() -> None:
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "fallback = last_valid_session_measurement(mem)" in source
    assert 'final_measurement_source="last_valid_session_state"' in source
    assert "event = self._finish_session_without_measurement(mem, cfg, session_ended_at)" in source
    assert "Missing post-close refresh feedback is not a rejection" in source


def test_resident_names_are_parsed_from_real_compact_setting_format() -> None:
    assert normalise_resident_names(" Paul, Lydia; Fiona\nMaya ") == ["Paul", "Lydia", "Fiona", "Maya"]
    assert normalise_resident_names(["Paul", "Paul", " Lydia "]) == ["Paul", "Lydia"]


def test_transport_redacts_string_resident_names_but_preserves_version_fields() -> None:
    export = {
        "freshairiq_version": "0.25.0.39",
        "field_test": {"anonymous_installation_id": "install-test"},
        "test_dossier": {
            "configuration": {
                "freshairiq_version": "0.25.0.39",
                "adult_resident_names": "Paul, Lydia",
                "child_resident_names": "Fiona, Maya",
            },
            "freshairiq_version_history": [{"version": "0.25.0.39", "record_count": 1}],
        },
        "records": [{
            "timestamp": "2026-09-18T10:00:00+02:00",
            "freshairiq_version": "0.25.0.39",
            "message": "Paul und Fiona sehen 192.168.1.5",
        }],
    }
    metadata, records = build_analysis_export(export)
    text = json.dumps({"metadata": metadata, "records": records}, ensure_ascii=False)
    assert "Paul" not in text
    assert "Lydia" not in text
    assert "Fiona" not in text
    assert "Maya" not in text
    assert "192.168.1.5" not in text
    assert "<redacted_ip>" in text
    assert metadata["freshairiq_version"] == "0.25.0.39"
    assert metadata["test_dossier"]["configuration"]["freshairiq_version"] == "0.25.0.39"
    assert metadata["test_dossier"]["freshairiq_version_history"][0]["version"] == "0.25.0.39"
    assert records[0]["freshairiq_version"] == "0.25.0.39"


def test_diagnostics_counts_people_not_characters() -> None:
    source = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    assert 'len(normalise_resident_names(options.get("adult_resident_names")))' in source
    assert 'len(normalise_resident_names(options.get("child_resident_names")))' in source
    assert 'len(options.get("adult_resident_names") or [])' not in source


def test_unmeasured_completion_notification_never_claims_zero_ml() -> None:
    source = (COMP / "notifications.py").read_text(encoding="utf-8")
    assert 'event.get("moisture_measurement_valid", event.get("removed_ml") is not None)' in source
    assert "Feuchtemessung war für eine belastbare Abschlussauswertung nicht ausreichend" in source


def test_android_harness_enforces_real_css_viewport_width() -> None:
    spec = (ROOT / "frontend_tests" / "freshairiq.spec.mjs").read_text(encoding="utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' in spec
    assert "expect(metrics.innerWidth).toBe(width);" in spec
    assert "expect(metrics.documentWidth).toBe(width);" in spec
    assert "el._hass.states['sensor.freshairiq_status']" in spec
    assert "el.hass.states['sensor.freshairiq_status']" not in spec
