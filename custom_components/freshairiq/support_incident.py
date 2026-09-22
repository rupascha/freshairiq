"""Privacy-safe support incident contracts for FreshAirIQ.

This module is deliberately pure and observational. It classifies already-produced
runtime/decision diagnostics for support and fleet-wide clustering; it never
changes ventilation decisions and never consumes Home Assistant entity IDs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SUPPORT_SCHEMA_VERSION = 1


def _text(value: Any, limit: int = 64) -> str:
    return str(value or "").strip()[:limit]


def _bool_failures(trace: Mapping[str, Any]) -> list[str]:
    invariants = trace.get("invariants") if isinstance(trace.get("invariants"), Mapping) else {}
    return sorted(str(key) for key, ok in invariants.items() if ok is False)


def _sensor_issue(sensor_quality: Mapping[str, Any] | None) -> bool:
    quality = sensor_quality if isinstance(sensor_quality, Mapping) else {}
    for key in ("invalid_rooms", "stale_rooms", "unusable_rooms", "error_rooms", "missing_rooms"):
        value = quality.get(key)
        if isinstance(value, (list, tuple, set)) and value:
            return True
        if isinstance(value, (int, float)) and value > 0:
            return True
    return False


def classify_support_code(
    decision_trace: Mapping[str, Any] | None,
    sensor_quality: Mapping[str, Any] | None = None,
    *,
    diagnostics_error_type: str | None = None,
    runtime_config_issues: list[str] | None = None,
) -> str | None:
    """Return a stable, documented support code or ``None`` for healthy state."""
    trace = decision_trace if isinstance(decision_trace, Mapping) else {}
    final = trace.get("final") if isinstance(trace.get("final"), Mapping) else {}
    failures = _bool_failures(trace)
    if diagnostics_error_type:
        return "FAIQ-DIAG-IO-001"
    if runtime_config_issues:
        return "FAIQ-CONFIG-RUNTIME-001"
    if failures:
        return "FAIQ-DECISION-INVARIANT-001"
    if _text(final.get("kind")) == "sensor" or _sensor_issue(sensor_quality):
        return "FAIQ-SENSOR-DATA-001"
    return None


def build_support_incident(
    decision_trace: Mapping[str, Any] | None,
    sensor_quality: Mapping[str, Any] | None = None,
    *,
    diagnostics_error_type: str | None = None,
    runtime_config_issues: list[str] | None = None,
) -> dict[str, Any]:
    """Build deterministic, privacy-safe support metadata for one diagnostic event."""
    trace = decision_trace if isinstance(decision_trace, Mapping) else {}
    final = trace.get("final") if isinstance(trace.get("final"), Mapping) else {}
    failures = _bool_failures(trace)
    issues = sorted({_text(item, 80) for item in (runtime_config_issues or []) if _text(item, 80)})[:20]
    error_type = _text(diagnostics_error_type, 80) or None
    code = classify_support_code(
        trace, sensor_quality, diagnostics_error_type=error_type, runtime_config_issues=issues
    )
    cluster = {
        "support_code": code or "HEALTHY",
        "decision_kind": _text(final.get("kind")),
        "decision_status": _text(final.get("status")),
        "decision_scope": _text(final.get("scope")),
        "failed_invariants": failures,
        "diagnostics_error_type": error_type,
        "runtime_config_issue_types": issues,
        "sensor_issue": _sensor_issue(sensor_quality),
    }
    raw = json.dumps(cluster, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    trace_raw = json.dumps(trace, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    return {
        "schema_version": SUPPORT_SCHEMA_VERSION,
        "support_code": code,
        "incident": code is not None,
        "fingerprint": f"faiq-{fingerprint}",
        "decision_trace_id": f"trace-{hashlib.sha256(trace_raw.encode('utf-8')).hexdigest()[:24]}",
        "classification": cluster,
        "privacy": {
            "contains_entity_ids": False,
            "contains_room_names": False,
            "contains_free_text": False,
        },
    }
