"""Privacy-safe local runtime incident aggregation for FreshAirIQ.

The monitor deliberately stores only technical classifications and counters.
Raw exception messages, entity ids, room names and log lines never enter this
structure. It is safe to include in the existing pseudonymised diagnostics
transport and lets the Hub correlate recurring product problems fleet-wide.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

RECORDER_ATTRIBUTE_LIMIT_BYTES = 16_384
ATTRIBUTE_WARNING_BYTES = 12_288
RUNTIME_HEALTH_SCHEMA_VERSION = 3
HEALTH_CONTRACT_VERSION = 1
_MAX_INCIDENTS = 32
_MAX_METRICS = 24
_MIN_BASELINE_SAMPLES = 8


def json_payload_bytes(value: Any) -> int:
    """Return deterministic UTF-8 JSON size for a Home Assistant payload."""
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return 0


def _stamp(value: datetime | str | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    return text[:64] or None


def _fingerprint(parts: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(parts), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return "runtime-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class RuntimeHealthMonitor:
    """Aggregate bounded, privacy-safe runtime incidents locally."""

    def __init__(self) -> None:
        self._incidents: dict[str, dict[str, Any]] = {}
        self._attribute_payloads: dict[str, dict[str, Any]] = {}
        self._metrics: dict[str, dict[str, Any]] = {}

    def _record(self, classification: Mapping[str, Any], evidence: Mapping[str, Any], now: datetime | str | None) -> None:
        fingerprint = _fingerprint(classification)
        timestamp = _stamp(now)
        row = self._incidents.get(fingerprint)
        if row is None:
            if len(self._incidents) >= _MAX_INCIDENTS:
                oldest = min(self._incidents, key=lambda key: str(self._incidents[key].get("last_seen_at") or ""))
                self._incidents.pop(oldest, None)
            row = {
                "fingerprint": fingerprint,
                "classification": dict(classification),
                "occurrences": 0,
                "first_seen_at": timestamp,
                "last_seen_at": timestamp,
                "evidence": {},
                "status": "active",
                "healthy_confirmations": 0,
                "resolved_at": None,
            }
            self._incidents[fingerprint] = row
        row["occurrences"] = min(int(row.get("occurrences") or 0) + 1, 2_147_483_647)
        row["last_seen_at"] = timestamp
        row["status"] = "active"
        row["healthy_confirmations"] = 0
        row["resolved_at"] = None
        merged = dict(row.get("evidence") or {})
        merged.update(dict(evidence))
        row["evidence"] = merged

    def observe_attribute_payload(
        self, logical_entity: str, attributes: Mapping[str, Any], now: datetime | str | None = None,
        *, recorder_exposed: bool = True,
    ) -> int:
        """Measure an own entity payload and flag only recorder-exposed oversize data."""
        size = json_payload_bytes(attributes)
        logical = str(logical_entity or "unknown")[:64]
        current = self._attribute_payloads.get(logical, {})
        self._attribute_payloads[logical] = {
            "logical_entity": logical,
            "last_attribute_bytes": size,
            "max_attribute_bytes": max(size, int(current.get("max_attribute_bytes") or 0)),
            "recorder_exposed": bool(recorder_exposed),
            "warning_threshold_bytes": ATTRIBUTE_WARNING_BYTES,
            "recorder_limit_bytes": RECORDER_ATTRIBUTE_LIMIT_BYTES,
            "last_seen_at": _stamp(now),
        }
        if not recorder_exposed or size < ATTRIBUTE_WARNING_BYTES:
            return size
        severity = "high" if size > RECORDER_ATTRIBUTE_LIMIT_BYTES else "medium"
        code = "FAIQ-HA-RECORDER-001" if size > RECORDER_ATTRIBUTE_LIMIT_BYTES else "FAIQ-HA-ATTR-SIZE-001"
        classification = {
            "support_code": code,
            "category": "state_attribute_size",
            "logical_entity": logical,
            "severity": severity,
        }
        existing = self._incidents.get(_fingerprint(classification), {})
        previous_max = int((existing.get("evidence") or {}).get("max_attribute_bytes") or 0)
        self._record(classification, {
            "max_attribute_bytes": max(size, previous_max),
            "warning_threshold_bytes": ATTRIBUTE_WARNING_BYTES,
            "recorder_limit_bytes": RECORDER_ATTRIBUTE_LIMIT_BYTES,
            "limit_exceeded": size > RECORDER_ATTRIBUTE_LIMIT_BYTES,
        }, now)
        return size

    def record_guardian_finding(self, finding: Mapping[str, Any], now: datetime | str | None = None) -> None:
        """Aggregate one privacy-safe Guardian invariant violation."""
        code = str(finding.get("code") or "FAIQ-GUARDIAN-UNKNOWN")[:80]
        classification = {
            "support_code": code,
            "category": "guardian_invariant",
            "component": str(finding.get("component") or "guardian")[:64],
            "invariant": str(finding.get("invariant") or "unknown")[:96],
            "severity": str(finding.get("severity") or "medium")[:16],
        }
        evidence = finding.get("evidence") if isinstance(finding.get("evidence"), Mapping) else {}
        safe_evidence = {str(k)[:64]: v for k, v in evidence.items() if isinstance(v, (bool, int, float, type(None)))}
        safe_evidence["auto_healable"] = bool(finding.get("auto_healable"))
        self._record(classification, safe_evidence, now)

    def reconcile_guardian_findings(
        self, findings: list[Mapping[str, Any]] | None, now: datetime | str | None = None, *, required_healthy_confirmations: int = 2,
    ) -> None:
        """Record current Guardian findings and resolve absent ones after confirmed health.

        Historical incidents are retained. Only Guardian incidents participate in
        this point-in-time reconciliation; unrelated runtime incidents keep their
        existing lifecycle. A recurrence reactivates the same fingerprint.
        """
        rows = [item for item in (findings or []) if isinstance(item, Mapping)]
        active_fingerprints: set[str] = set()
        for finding in rows:
            code = str(finding.get("code") or "FAIQ-GUARDIAN-UNKNOWN")[:80]
            classification = {
                "support_code": code,
                "category": "guardian_invariant",
                "component": str(finding.get("component") or "guardian")[:64],
                "invariant": str(finding.get("invariant") or "unknown")[:96],
                "severity": str(finding.get("severity") or "medium")[:16],
            }
            active_fingerprints.add(_fingerprint(classification))
            self.record_guardian_finding(finding, now)

        required = max(int(required_healthy_confirmations), 1)
        timestamp = _stamp(now)
        for fingerprint, row in self._incidents.items():
            classification = row.get("classification") if isinstance(row.get("classification"), Mapping) else {}
            if classification.get("category") != "guardian_invariant" or fingerprint in active_fingerprints:
                continue
            if str(row.get("status") or "active") == "resolved":
                continue
            confirmations = min(int(row.get("healthy_confirmations") or 0) + 1, required)
            row["healthy_confirmations"] = confirmations
            if confirmations >= required:
                row["status"] = "resolved"
                row["resolved_at"] = timestamp

    def record_exception(self, component: str, operation: str, error: BaseException, now: datetime | str | None = None) -> None:
        """Aggregate an unknown FreshAirIQ exception without its message/trace."""
        classification = {
            "support_code": "FAIQ-RUNTIME-UNKNOWN-001",
            "category": "runtime_exception",
            "component": str(component or "unknown")[:64],
            "operation": str(operation or "unknown")[:64],
            "error_type": type(error).__name__[:80],
            "severity": "high",
        }
        self._record(classification, {"error_type": type(error).__name__[:80]}, now)


    def observe_metric(
        self, metric: str, value: float | int, now: datetime | str | None = None,
        *, unit: str = "", higher_is_worse: bool = True,
    ) -> None:
        """Learn a bounded local baseline and flag large runtime deviations.

        Only aggregate statistics leave the runtime monitor; raw samples are not
        retained.  A baseline needs several observations before it can emit an
        anomaly, which avoids noisy startup findings.
        """
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return
        if numeric < 0 or numeric != numeric or numeric in (float("inf"), float("-inf")):
            return
        name = str(metric or "unknown")[:64]
        row = self._metrics.get(name)
        if row is None:
            if len(self._metrics) >= _MAX_METRICS:
                return
            row = {
                "metric": name, "unit": str(unit or "")[:16], "samples": 0,
                "mean": 0.0, "m2": 0.0, "min": numeric, "max": numeric,
                "last": numeric, "last_seen_at": _stamp(now), "anomalies": 0,
            }
            self._metrics[name] = row

        samples = int(row.get("samples") or 0)
        mean = float(row.get("mean") or 0.0)
        m2 = float(row.get("m2") or 0.0)
        stddev = (m2 / max(samples - 1, 1)) ** 0.5 if samples >= 2 else 0.0
        ratio = numeric / max(mean, 1e-9) if mean > 0 else 1.0
        z_score = (numeric - mean) / stddev if stddev > 1e-9 else 0.0
        anomalous = samples >= _MIN_BASELINE_SAMPLES and (
            (higher_is_worse and ratio >= 2.5 and z_score >= 4.0)
            or ((not higher_is_worse) and mean > 0 and numeric <= mean * 0.4 and z_score <= -4.0)
        )
        if anomalous:
            classification = {
                "support_code": "FAIQ-RUNTIME-ANOMALY-001",
                "category": "runtime_anomaly",
                "metric": name,
                "severity": "medium",
            }
            self._record(classification, {
                "baseline_samples": samples,
                "baseline_mean": round(mean, 3),
                "observed": round(numeric, 3),
                "ratio_to_baseline": round(ratio, 3),
                "z_score": round(z_score, 2),
                "unit": str(unit or "")[:16],
            }, now)
            row["anomalies"] = min(int(row.get("anomalies") or 0) + 1, 2_147_483_647)

        new_samples = min(samples + 1, 1_000_000)
        delta = numeric - mean
        new_mean = mean + delta / new_samples
        new_m2 = m2 + delta * (numeric - new_mean)
        row.update({
            "samples": new_samples, "mean": new_mean, "m2": new_m2,
            "min": min(float(row.get("min", numeric)), numeric),
            "max": max(float(row.get("max", numeric)), numeric),
            "last": numeric, "last_seen_at": _stamp(now),
        })

    def health_snapshot(self, now: datetime | str | None = None) -> dict[str, Any]:
        """Return a point-in-time, privacy-safe support/telemetry health snapshot."""
        snap = self.snapshot
        snap["captured_at"] = _stamp(now)
        return snap

    @property
    def user_summary(self) -> dict[str, Any]:
        """Return a compact screenshot-safe view of active support incidents.

        This intentionally exposes only stable support codes and technical
        classifications already stripped of names, entity IDs and messages.
        """
        active = []
        for row in sorted(self._incidents.values(), key=lambda item: str(item.get("last_seen_at") or ""), reverse=True):
            if str(row.get("status") or "active") == "resolved":
                continue
            classification = row.get("classification") if isinstance(row.get("classification"), Mapping) else {}
            active.append({
                "code": str(classification.get("support_code") or "FAIQ-RUNTIME-UNKNOWN-001")[:80],
                "category": str(classification.get("category") or "runtime")[:64],
                "component": str(classification.get("component") or classification.get("metric") or "FreshAirIQ")[:64],
                "operation": str(classification.get("operation") or classification.get("invariant") or "")[:96],
                "error_type": str(classification.get("error_type") or "")[:80],
                "severity": str(classification.get("severity") or "medium")[:16],
                "occurrences": int(row.get("occurrences") or 0),
                "last_seen_at": row.get("last_seen_at"),
            })
            if len(active) >= 5:
                break
        return {"active_problem": bool(active), "active_count": sum(1 for row in self._incidents.values() if str(row.get("status") or "active") != "resolved"), "incidents": active}

    @property
    def snapshot(self) -> dict[str, Any]:
        incidents = sorted(
            (dict(row) for row in self._incidents.values()),
            key=lambda row: (str(row.get("last_seen_at") or ""), str(row.get("fingerprint") or "")),
            reverse=True,
        )
        metrics = []
        for key in sorted(self._metrics):
            row = self._metrics[key]
            samples = int(row.get("samples") or 0)
            m2 = float(row.get("m2") or 0.0)
            metrics.append({
                "metric": row.get("metric"), "unit": row.get("unit"), "samples": samples,
                "mean": round(float(row.get("mean") or 0.0), 3),
                "stddev": round((m2 / max(samples - 1, 1)) ** 0.5, 3) if samples >= 2 else 0.0,
                "min": round(float(row.get("min") or 0.0), 3),
                "max": round(float(row.get("max") or 0.0), 3),
                "last": round(float(row.get("last") or 0.0), 3),
                "anomalies": int(row.get("anomalies") or 0),
                "last_seen_at": row.get("last_seen_at"),
            })
        active_incidents = [row for row in incidents if str(row.get("status") or "active") != "resolved"]
        return {
            "schema_version": RUNTIME_HEALTH_SCHEMA_VERSION,
            "health_contract_version": HEALTH_CONTRACT_VERSION,
            "incident_count": len(incidents),
            "active_incident_count": len(active_incidents),
            "resolved_incident_count": len(incidents) - len(active_incidents),
            "active_problem": bool(active_incidents),
            "incidents": incidents,
            "attribute_payloads": [dict(self._attribute_payloads[key]) for key in sorted(self._attribute_payloads)],
            "metric_baselines": metrics,
            "privacy": {
                "contains_entity_ids": False,
                "contains_room_names": False,
                "contains_exception_messages": False,
                "contains_log_lines": False,
            },
        }
