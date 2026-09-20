"""Static contracts for v0.25.0.41 Diagnostics Client Hardening."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def test_version_and_hub_are_scoped_to_private_local_staging():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert 'VERSION = "0.25.0.41"' in const
    assert manifest["version"] == "0.25.0.41"
    assert 'DIAGNOSTICS_HUB_ENDPOINT = "https://diagnostics.freshairiq.com"' in const


def test_manual_diagnostics_export_path_is_still_present_and_independent():
    diagnostics = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert "async def async_export" in diagnostics
    assert 'url = "/api/freshairiq/diagnostics"' in diagnostics
    assert 'id="diagnostics-export"' in card
    assert "<b>Diagnosedaten</b><span>exportieren</span>" in card
    assert 'callApi("GET", "freshairiq/diagnostics")' in card


def test_runtime_client_uses_chunking_incremental_cursor_and_idempotency():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert "build_upload_chunks" in telemetry
    assert "DEFAULT_MAX_UPLOAD_RECORDS" not in telemetry
    assert 'after_cursor=self._state.get("last_record_cursor")' in telemetry
    assert 'self._state["last_record_cursor"] = chunk.get("cursor_after")' in telemetry
    assert '"Idempotency-Key": str(chunk.get("chunk_id") or "")' in telemetry
    assert '"X-FreshAirIQ-Chunk-ID"' in telemetry
    assert '"X-FreshAirIQ-Batch-ID"' in telemetry


def test_transport_v2_declares_analysis_equivalence_and_no_history_trimming():
    transport = (COMP / "diagnostic_transport.py").read_text(encoding="utf-8")
    assert "UPLOAD_SCHEMA_VERSION = 2" in transport
    assert '"analysis_equivalent": True' in transport
    assert '"full_retained_history": True' in transport
    assert '"incremental_after_first_ack": True' in transport
    assert "build_upload_chunks" in transport
    assert "select_records_after_cursor" in transport
    assert "record_ids" in transport


def test_quality_policy_requires_hardening_contract_and_release_suffix():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    assert policy["version"] == "0.25.0.41"
    assert "tests/test_diagnostics_client_hardening_025023.py" in policy["robustness"]["required_test_files"]
    assert policy["release"]["artifact_suffix"] == "Maximum-Hardening-Hotfix"
