"""Final decision trace and objective recommendation-quality evidence.

The trace is observational: it never changes the canonical FreshAirIQ action.
It is attached only after all decision, aggregation, personalisation and opening
strategy layers have finished, so diagnostics can explain the exact decision
that reached the user.
"""
from __future__ import annotations

from math import isfinite
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if isfinite(number) else default


def _bounded_confidence(value: Any) -> int:
    return round(min(max(_f(value), 0.0), 100.0))


def build_recommendation_quality(validation: dict[str, Any] | None) -> dict[str, Any]:
    """Convert objective forecast validation into a conservative quality state."""
    source = validation if isinstance(validation, dict) else {}
    samples = max(int(_f(source.get("valid_record_count"))), 0)
    direction = source.get("direction_accuracy_percent")
    moisture_mae = source.get("moisture_mae_ml")
    close_mae = source.get("close_time_mae_min")

    evidence = "insufficient"
    if samples >= 30:
        evidence = "strong"
    elif samples >= 12:
        evidence = "established"
    elif samples >= 5:
        evidence = "developing"

    metrics_available = sum(value is not None for value in (direction, moisture_mae, close_mae))
    calibrated = samples >= 12 and metrics_available >= 2
    return {
        "version": "v1",
        "evidence_level": evidence,
        "calibrated": calibrated,
        "validated_sessions": samples,
        "direction_accuracy_percent": round(_f(direction), 1) if direction is not None else None,
        "moisture_mae_ml": round(_f(moisture_mae), 1) if moisture_mae is not None else None,
        "close_time_mae_min": round(_f(close_mae), 2) if close_mae is not None else None,
        "timeline_improvement_percent": round(_f(source.get("timeline_improvement_percent")), 1)
        if source.get("timeline_improvement_percent") is not None else None,
    }


def build_decision_trace(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    *,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic trace of the already-final recommendation."""
    rec = recommendation if isinstance(recommendation, dict) else {}
    brain = rec.get("decision_brain") if isinstance(rec.get("decision_brain"), dict) else {}
    kind = str(rec.get("kind") or "okay")
    status = str(rec.get("status") or "")
    scope = str(rec.get("presentation_scope") or "rooms")
    room_keys = [str(key) for key in (rec.get("room_keys") or []) if str(key) in rooms]

    candidates: list[dict[str, Any]] = []
    short = list(rec.get("simulated_options") or [])
    plan = rec.get("day_night_plan") if isinstance(rec.get("day_night_plan"), dict) else {}
    for item in short[:8]:
        if not isinstance(item, dict):
            continue
        candidates.append({
            "source": "short_term",
            "id": str(item.get("id") or ""),
            "score": round(_f(item.get("score")), 2) if item.get("score") is not None else None,
            "removed_ml": round(_f(item.get("removed_ml")), 1) if item.get("removed_ml") is not None else None,
            "confidence": _bounded_confidence(item.get("confidence")),
            "selected": str(item.get("id") or "") == str(rec.get("selected_option_id") or ""),
        })
    for item in list(plan.get("options") or [])[:8]:
        if not isinstance(item, dict):
            continue
        candidates.append({
            "source": "day_night_plan",
            "id": str(item.get("id") or ""),
            "score": round(_f(item.get("score")), 2) if item.get("score") is not None else None,
            "removed_ml": round(_f(item.get("projected_potential_ml", item.get("removed_ml"))), 1)
            if item.get("projected_potential_ml", item.get("removed_ml")) is not None else None,
            "confidence": _bounded_confidence(item.get("confidence", plan.get("confidence"))),
            "selected": str(item.get("id") or "") == str(plan.get("selected_option_id") or ""),
        })

    overrides: list[dict[str, Any]] = []
    night = brain.get("night_strategy") if isinstance(brain.get("night_strategy"), dict) else {}
    if night.get("active"):
        overrides.append({
            "strategy": "night_strategy",
            "active": True,
            "won": bool(brain.get("night_strategy_primary", rec.get("night_strategy_primary", False))),
            "action": str(night.get("action") or ""),
        })
    if scope in {"house", "floor"}:
        overrides.append({
            "strategy": f"{scope}_aggregation",
            "active": True,
            "won": True,
            "action": kind,
        })
    if status == "passive_open_monitor":
        overrides.append({"strategy": "passive_open_monitor", "active": True, "won": True, "action": kind})
    if kind == "pollen_wait":
        overrides.append({"strategy": "pollen_veto", "active": True, "won": True, "action": kind})
    if kind == "sensor":
        overrides.append({"strategy": "sensor_safety", "active": True, "won": True, "action": kind})

    confidence = brain.get("impact", {}).get("confidence") if isinstance(brain.get("impact"), dict) else None
    if confidence is None:
        confidence = rec.get("forecast_confidence", rec.get("confidence", 0))

    return {
        "version": "v1",
        "observational_only": True,
        "final": {
            "kind": kind,
            "status": status,
            "scope": scope,
            "room_keys": room_keys,
            "duration_min": round(_f(rec.get("duration_min")), 2) if rec.get("duration_min") is not None else None,
            "confidence": _bounded_confidence(confidence),
            "decision_label": str(brain.get("decision_label") or ""),
        },
        "evidence": {
            "candidate_count": len(candidates),
            "candidates": candidates,
            "overrides": overrides,
            "forecast_validation": build_recommendation_quality(validation),
        },
        "invariants": {
            "final_action_matches_brain": not brain or str(brain.get("action_line") or "") == str(rec.get("instruction") or ""),
            "final_headline_matches_brain": not brain or str(brain.get("headline") or "") == str(rec.get("title") or ""),
            "selected_rooms_exist": len(room_keys) == len([key for key in (rec.get("room_keys") or []) if str(key)]),
        },
    }
