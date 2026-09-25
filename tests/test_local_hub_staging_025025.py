"""Regression contracts for v0.25.0.75 local Hub staging connection."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def test_release_is_scoped_to_the_private_staging_hub_and_remains_opt_in():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert 'VERSION = "0.25.0.75"' in const
    assert manifest["version"] == "0.25.0.75"
    assert 'DIAGNOSTICS_HUB_ENDPOINT = "https://diagnostics.freshairiq.com"' in const
    assert '"diagnostics_reporting_mode": "daily"' in const


def test_client_matches_hub_v03_enrollment_and_authenticated_chunk_contract():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert 'self.enroll_endpoint = f"{self.endpoint}/v1/enroll"' in telemetry
    assert 'self.upload_endpoint = f"{self.endpoint}/v1/diagnostics/chunks"' in telemetry
    assert '"anonymous_installation_id": installation_id' in telemetry
    assert '"client_token": token' in telemetry
    assert '"upload_schema_version": 2' in telemetry
    assert '"Authorization": f"Bearer {token}"' in telemetry
    assert '"Idempotency-Key": str(chunk.get("chunk_id") or "")' in telemetry


def test_client_credential_is_persisted_before_enrollment_but_never_exposed_in_status():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert 'self._state["client_token"] = token' in telemetry
    assert 'if not await self._save_state()' in telemetry
    status_block = telemetry.split("def status", 1)[1].split("async def async_start", 1)[0]
    assert '"client_token"' not in status_block
    assert '"hub_enrolled"' in status_block


def test_plain_http_is_explicitly_limited_to_private_or_loopback_addresses():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert 'parsed.scheme == "http"' in telemetry
    assert "ipaddress.ip_address(host)" in telemetry
    assert "address.is_private or address.is_loopback" in telemetry
    assert 'parsed.scheme not in {"http", "https"}' in telemetry


def test_first_explicit_daily_or_weekly_opt_in_can_sync_immediately():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert 'first_sync_due = not self._state.get("last_success_at")' in telemetry
    assert 'mode in {"daily", "weekly"} or current_problem is not None' in telemetry
    # Off is still checked before identity/export/enrollment.
    assert 'if mode == "off":' in telemetry


def test_live_settings_change_requests_an_immediate_nonblocking_upload_check():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    settings_api = (COMP / "settings_api.py").read_text(encoding="utf-8")
    config_flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert "def request_check" in telemetry
    assert 'trigger_diagnostics_check=key == "diagnostics_reporting_mode"' in settings_api
    assert "coordinator.telemetry.request_check()" in settings_api
    assert 'if "diagnostics_reporting_mode" in changed_option_keys' in config_flow
    assert "coordinator.telemetry.request_check()" in config_flow


def test_release_quality_gate_requires_the_staging_contract():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    assert policy["version"] == "0.25.0.75"
    assert "tests/test_local_hub_staging_025025.py" in policy["robustness"]["required_test_files"]
    assert str(policy["release"]["artifact_suffix"]).strip()
