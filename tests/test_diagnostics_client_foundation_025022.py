"""Static integration contracts for v0.25.0.47 Diagnostics Client Foundation."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def test_remote_diagnostics_is_opt_in_and_local_staging_endpoint_is_explicit():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    assert 'VERSION = "0.25.0.47"' in const
    assert 'DIAGNOSTICS_HUB_ENDPOINT = "https://diagnostics.freshairiq.com"' in const
    assert '"diagnostics_reporting_mode": "off"' in const
    assert '"diagnostics_include_client_context": False' in const
    assert 'DIAGNOSTICS_UPLOAD_MAX_BYTES = 2 * 1024 * 1024' in const


def test_coordinator_owns_client_and_starts_and_stops_it_with_runtime():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "FreshAirIQDiagnosticsClient" in coordinator
    assert "await self.telemetry.async_start()" in coordinator
    assert "await self.telemetry.async_stop()" in coordinator
    assert 'data["diagnostics_upload"] = self.telemetry.status' in coordinator


def test_native_and_dashboard_settings_expose_same_reporting_preferences():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    contract = (COMP / "settings_contract.py").read_text(encoding="utf-8")
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    for key in ("diagnostics_reporting_mode", "diagnostics_include_client_context"):
        assert key in flow
        assert key in contract
        assert key in card
    assert "diagnostics_sharing" in flow
    assert "diagnostics_sharing" in card
    assert "Hub-Status: lokales Staging verbunden" in card


def test_diagnostics_identity_can_be_reused_without_full_export():
    diagnostics = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    assert "async def async_get_identity" in diagnostics
    assert "_load_or_create_field_test_identity" in diagnostics


def test_transport_module_is_pure_and_telemetry_module_is_excluded_from_pure_coverage():
    transport = (COMP / "diagnostic_transport.py").read_text(encoding="utf-8")
    assert "homeassistant" not in transport
    coverage = (ROOT / ".coveragerc-pure").read_text(encoding="utf-8")
    assert "custom_components/freshairiq/telemetry.py" in coverage
    assert "custom_components/freshairiq/diagnostic_transport.py" not in coverage


def test_release_policy_makes_transport_privacy_tests_part_of_robustness_gate():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    assert policy["version"] == "0.25.0.47"
    assert "tests/test_diagnostics_transport_025022.py" in policy["robustness"]["required_test_files"]
    assert policy["release"]["artifact_suffix"] == "Release-Asset-Changelog-Hygiene-Hotfix"
