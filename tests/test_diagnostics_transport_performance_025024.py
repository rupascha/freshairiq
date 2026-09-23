"""Regression contracts for v0.25.0.58 diagnostics transport performance hotfix."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from custom_components.freshairiq import diagnostic_transport as transport

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def _large_export(count: int = 120) -> dict:
    return {
        "schema_version": 10,
        "freshairiq_version": "0.25.0.58",
        "exported_at": "2026-09-17T08:00:00+00:00",
        "field_test": {
            "anonymous_installation_id": "faiq-install-performance",
            "runtime_environment": {"home_assistant_version": "2026.9.2"},
            "observation": {"record_count": count},
            "freshairiq_version_history": [],
            "home_assistant_version_history": [],
            "known_clients": [],
        },
        "test_dossier": {
            "record_count": count,
            "configuration": {
                "rooms": [{"key": "living", "name": "Private Living", "volume_m3": 80.0}]
            },
            "forecast_validation": {},
            "forecast_backtest": {},
        },
        "records": [
            {
                "timestamp": f"2026-09-17T08:{index % 60:02d}:{index % 59:02d}+00:00",
                "rooms": [{"key": "living", "name": "Private Living", "temperature": 21.0}],
                "blob": "x" * 3000,
                "sequence": index,
            }
            for index in range(count)
        ],
    }


def test_release_version_and_private_staging_endpoint_are_fixed():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert 'VERSION = "0.25.0.58"' in const
    assert manifest["version"] == "0.25.0.58"
    assert 'DIAGNOSTICS_HUB_ENDPOINT = "https://diagnostics.freshairiq.com"' in const


def test_ha_client_offloads_chunk_build_and_compression_from_event_loop():
    telemetry = (COMP / "telemetry.py").read_text(encoding="utf-8")
    assert "async def _async_cpu_job" in telemetry
    assert 'getattr(self.hass, "async_add_executor_job", None)' in telemetry
    assert "return await asyncio.to_thread(job)" in telemetry
    assert "chunks = await self._async_cpu_job(" in telemetry
    assert "build_upload_chunks," in telemetry
    assert "compressed = await self._async_cpu_job(_encode_chunk_for_upload, chunk)" in telemetry
    assert "compresslevel=_GZIP_COMPRESSLEVEL" in telemetry


def test_partitioning_is_linear_in_final_chunk_count(monkeypatch):
    source = _large_export(120)
    original = transport._build_chunk_document
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(transport, "_build_chunk_document", counted)
    chunks = transport.build_upload_chunks(source, max_chunk_bytes=64 * 1024)
    assert len(chunks) > 1
    # One empty sizing probe plus one build per final chunk. The old quadratic
    # implementation called this once for almost every growing record candidate.
    assert calls <= len(chunks) + 2
    assert sum(len(chunk["records"]) for chunk in chunks) == 120
    assert all(transport._chunk_payload_size(chunk) <= 64 * 1024 for chunk in chunks)


def test_analysis_export_no_longer_needs_deepcopy_but_never_mutates_source():
    source = _large_export(8)
    before = deepcopy(source)
    metadata, records = transport.build_analysis_export(source)
    assert source == before
    assert len(records) == 8
    text = json.dumps({"metadata": metadata, "records": records}, ensure_ascii=False)
    assert "Private Living" not in text
    assert '"living"' not in text
