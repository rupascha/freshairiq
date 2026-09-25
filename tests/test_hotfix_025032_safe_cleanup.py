"""Regression contracts for v0.25.0.72 safe code cleanup."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def test_release_version_and_cleanup_suffix_are_consistent():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    assert 'VERSION = "0.25.0.72"' in const
    assert manifest["version"] == "0.25.0.72"
    assert policy["version"] == "0.25.0.72"
    assert str(policy["release"]["artifact_suffix"]).strip()


def test_removed_config_helpers_are_replaced_by_active_unified_schemas():
    text = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert "def _personalisation_schema(" not in text
    assert "def _house_schema(" not in text
    assert "def _building_schema(" in text
    assert "def _residents_schema(" in text
    assert 'vol.Optional("personalisation")' in text


def test_timestamp_learning_gate_stays_direct_and_unchanged():
    text = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert 'session_activity_eligible = bool(session_quality.get("timestamp_gate_passed"))' in text
    assert "frame_learning_eligible = session_activity_eligible" in text
    assert "session_activity_eligible and end_frame_eligible" not in text
    assert "start_frame_eligible =" not in text
    assert "end_frame_eligible =" not in text


def test_diagnostics_hub_and_diagnostics_ha_compatibility_surface_is_preserved():
    transport = (COMP / "diagnostic_transport.py").read_text(encoding="utf-8")
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    diagnostics = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    settings_api = (COMP / "settings_api.py").read_text(encoding="utf-8")

    # Hub upload v2 + resumable cursor contract.
    assert "UPLOAD_SCHEMA_VERSION = 2" in transport
    assert "CURSOR_SCHEMA_VERSION = 1" in transport
    for public_name in (
        "build_cloud_payload",       # legacy/public compatibility
        "build_upload_chunks",       # active Hub v2 transport
        "record_cursor",             # resumable acknowledgement state
        "select_records_after_cursor",
    ):
        tree = ast.parse(transport)
        assert any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == public_name for node in tree.body)

    assert 'self.enroll_endpoint = f"{self.endpoint}/v1/enroll"' in telemetry
    assert 'self.upload_endpoint = f"{self.endpoint}/v1/diagnostics/chunks"' in telemetry
    assert 'f"{self.endpoint}/v1/feedback"' in telemetry
    assert '"Authorization": f"Bearer {token}"' in telemetry
    assert '"Idempotency-Key": str(chunk.get("chunk_id") or "")' in telemetry

    # Manual/HA diagnostics and explicit feedback proxy remain stable.
    assert 'url = "/api/freshairiq/diagnostics"' in diagnostics
    assert 'url = "/api/freshairiq/feedback/{entry_id}"' in settings_api
    assert "from .const import DIAGNOSTICS_SCHEMA_VERSION" in diagnostics


def test_cleanup_does_not_remove_diagnostics_files_or_migration_paths():
    for relative in (
        "diagnostics.py", "diagnostic_transport.py", "telemetry.py", "settings_api.py", "storage.py", "config_flow.py"
    ):
        assert (COMP / relative).is_file()

    config = (COMP / "config_flow.py").read_text(encoding="utf-8")
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert "async_migrate_entry" in init or "async_migrate_entry" in config
