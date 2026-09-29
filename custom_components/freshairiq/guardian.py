"""FreshAirIQ Guardian: deterministic runtime invariants and safe self-healing.

This module is intentionally pure: it only consumes privacy-safe runtime state and
returns findings plus narrowly-scoped reversible repairs. It never mutates Home
Assistant configuration, entity assignments or learned user preferences.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

GUARDIAN_SCHEMA_VERSION = 1

@dataclass(frozen=True, slots=True)
class GuardianFinding:
    code: str
    severity: str
    invariant: str
    component: str
    evidence: dict[str, Any]
    auto_healable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def evaluate_guardian(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Evaluate invariants without user-identifying evidence.

    Evidence deliberately contains counts/booleans/numeric boundaries only. Room
    names, entity ids and arbitrary exception text are never emitted.
    """
    state = data if isinstance(data, Mapping) else {}
    findings: list[GuardianFinding] = []
    repairs: list[dict[str, Any]] = []

    rooms = state.get("rooms") if isinstance(state.get("rooms"), Mapping) else {}
    invalid_rooms = 0
    contradictory_rooms = 0
    for room in rooms.values():
        if not isinstance(room, Mapping):
            invalid_rooms += 1
            continue
        temp = _num(room.get("temperature"))
        rh = _num(room.get("humidity"))
        ah = _num(room.get("absolute_humidity"))
        if (temp is not None and not -40 <= temp <= 80) or (rh is not None and not 0 <= rh <= 100) or (ah is not None and not 0 <= ah <= 80):
            invalid_rooms += 1
        canonical = str(room.get("canonical_action") or room.get("canonical_recommendation") or "").lower()
        visible = str(room.get("action") or "").lower()
        if canonical and visible:
            keep = any(token in canonical for token in ("keep", "continue", "open", "monitor"))
            close = "close" in visible or "schließ" in visible
            if keep and close:
                contradictory_rooms += 1
    if invalid_rooms:
        findings.append(GuardianFinding("FAIQ-GUARDIAN-SENSOR-001", "high", "room_measurements_physical_range", "measurement", {"affected_room_count": invalid_rooms}))
    if contradictory_rooms:
        findings.append(GuardianFinding("FAIQ-GUARDIAN-DECISION-001", "high", "canonical_visible_recommendation_consistency", "recommendation", {"affected_room_count": contradictory_rooms}))

    # Forecast monotonicity: cumulative moisture effect must not decrease when the
    # same start state is projected further into the future.
    timeline = state.get("forecast_timeline")
    if not isinstance(timeline, list):
        timeline = (state.get("forecast_validation") or {}).get("timeline") if isinstance(state.get("forecast_validation"), Mapping) else []
    points: list[tuple[float, float]] = []
    if isinstance(timeline, list):
        for row in timeline:
            if not isinstance(row, Mapping):
                continue
            minute = _num(row.get("minutes") if "minutes" in row else row.get("duration_min"))
            effect = _num(row.get("moisture_effect_ml") if "moisture_effect_ml" in row else row.get("predicted_removed_ml"))
            if minute is not None and effect is not None and minute >= 0:
                points.append((minute, effect))
    points.sort()
    if any(points[i][1] + 1e-6 < points[i-1][1] for i in range(1, len(points))):
        findings.append(GuardianFinding("FAIQ-GUARDIAN-FORECAST-001", "high", "cumulative_forecast_monotonicity", "forecast", {"forecast_points": len(points)}))

    recovery = state.get("sensor_recovery") if isinstance(state.get("sensor_recovery"), Mapping) else {}
    unavailable = int(recovery.get("required_sources_unavailable") or 0)
    valid_cycles = int(recovery.get("valid_cycles") or 0)
    required_cycles = max(int(recovery.get("required_valid_cycles") or 0), 0)
    if unavailable > 0 and not bool(recovery.get("active")):
        findings.append(GuardianFinding("FAIQ-GUARDIAN-SENSOR-002", "medium", "unavailable_sources_require_recovery_guard", "sensor_recovery", {"unavailable_source_count": unavailable}))
    if unavailable == 0 and bool(recovery.get("active")) and required_cycles and valid_cycles >= required_cycles:
        findings.append(GuardianFinding("FAIQ-GUARDIAN-RECOVERY-001", "low", "completed_recovery_must_clear", "sensor_recovery", {"valid_cycles": valid_cycles, "required_valid_cycles": required_cycles}, True))
        repairs.append({"repair": "clear_completed_sensor_recovery", "safe": True, "reversible": True})

    learning_v2 = state.get("learning_v2") if isinstance(state.get("learning_v2"), Mapping) else {}
    if bool(learning_v2.get("drift_detected")):
        findings.append(GuardianFinding("FAIQ-GUARDIAN-LEARNING-001", "high", "learned_model_must_not_override_regressing_evidence", "learning_v2", {"physics_fallback_rooms": int(learning_v2.get("physics_fallback_rooms") or 0)}))
    lv2_confidence = _num(learning_v2.get("confidence_percent"))
    lv2_maturity = _num(learning_v2.get("maturity_percent"))
    if lv2_confidence is not None and lv2_maturity is not None and lv2_maturity >= 85 and lv2_confidence < 40:
        findings.append(GuardianFinding("FAIQ-GUARDIAN-LEARNING-002", "medium", "high_maturity_requires_calibrated_confidence", "learning_v2", {"maturity_percent": round(lv2_maturity, 1), "confidence_percent": round(lv2_confidence, 1)}))

    finalizing = state.get("finalizing_measurements")
    if isinstance(finalizing, Mapping):
        pending = int(finalizing.get("pending_rooms") or finalizing.get("pending_count") or 0)
        if pending < 0:
            findings.append(GuardianFinding("FAIQ-GUARDIAN-SESSION-001", "high", "pending_finalization_count_nonnegative", "session", {"pending_count_invalid": True}))

    return {
        "schema_version": GUARDIAN_SCHEMA_VERSION,
        "status": "attention" if findings else "healthy",
        "finding_count": len(findings),
        "high_count": sum(f.severity in {"high", "critical"} for f in findings),
        "auto_heal_candidate_count": sum(f.auto_healable for f in findings),
        "findings": [f.as_dict() for f in findings],
        "safe_repairs": repairs,
        "privacy": {"contains_entity_ids": False, "contains_room_names": False, "contains_free_text": False},
    }
