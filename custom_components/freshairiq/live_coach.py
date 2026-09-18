"""FreshAirIQ self-learning live ventilation coach.

Re-evaluates an already running ventilation session. It never starts a session
and never overrides sensor errors. Health/safety and the existing physical
close rules remain authoritative.
"""
from __future__ import annotations
from typing import Any
from math import isfinite


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def refine_live_recommendation(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    """Adapt remaining time from actual session progress and marginal benefit."""
    active = [r for r in rooms.values()
              if r.get("calculation_enabled", True)
              and r.get("data_quality") == "ok"
              and r.get("active")]
    if not active or str(recommendation.get("kind") or "") not in {"continue", "close"}:
        return recommendation

    # Existing close decision is authoritative; we only enrich its explanation.
    if str(recommendation.get("kind") or "") == "close":
        out = dict(recommendation)
        out["live_coach"] = True
        out["live_coach_state"] = "close"
        out["live_coach_reason"] = "Physikalisches Schließkriterium erreicht"
        # Hotfix 0.19.1.1: a close recommendation is an immediate action.  Do
        # not leave a stale positive remaining time from the previous house
        # target in the dashboard (e.g. "Jetzt schließen" and "1 min bis Ziel"
        # at the same time).
        out["live_coach_remaining_min"] = 0.0
        out["live_coach_confidence"] = min(
            [int(r.get("forecast_5_min_confidence", r.get("forecast_confidence", 0)) or 0) for r in active] or [0]
        )
        return out

    elapsed = max((_f(r.get("session_elapsed_min")) for r in active), default=0.0)
    min_duration = max(_f(options.get("min_duration_min"), 3.0), 2.0)
    max_duration = max(_f(options.get("max_duration_min"), 20.0), min_duration)

    # Original learned target attached when the recommendation was followed.
    linked_targets = [
        _f(r.get("session_recommended_duration_min"))
        for r in active if r.get("session_recommended_duration_min") is not None
    ]
    baseline_target = (
        sum(linked_targets) / len(linked_targets)
        if linked_targets else elapsed + max(_f(recommendation.get("duration_min"), 1.0), 1.0)
    )
    baseline_target = _clamp(baseline_target, min_duration, max_duration)

    predicted_totals = [
        _f(r.get("session_predicted_removed_ml"))
        for r in active if _f(r.get("session_predicted_removed_ml")) > 20
    ]
    predicted_total = sum(predicted_totals)
    actual_removed = sum(max(_f(r.get("result_ml")), 0.0) for r in active)
    next5 = sum(max(_f(r.get("forecast_5_min_moisture_effect_ml",
                             r.get("moisture_effect_next_5_min_ml"))), 0.0) for r in active)
    next5_temp = (
        sum(_f(r.get("forecast_5_min_temperature_change_c")) * max(_f(r.get("volume_m3")), 1.0) for r in active)
        / max(sum(max(_f(r.get("volume_m3")), 1.0) for r in active), 1.0)
    )
    confidence = min(
        [int(r.get("forecast_5_min_confidence", r.get("forecast_confidence", 0)) or 0) for r in active] or [0]
    )

    # Hotfix 0.17.0.5: the live coach may adapt duration, but it must never
    # manufacture a close recommendation for rooms whose room model has not
    # yet released the two-report / 15-minute close-decision gate. Because a
    # live-coach close instruction targets all active rooms, all of them must be
    # decision-ready before the coach may turn ``continue`` into ``close``.
    all_close_decisions_ready = all(bool(r.get("close_decision_ready", False)) for r in active)

    # Progress ratio compares real removal with what should have been achieved
    # by this point on the originally recommended trajectory.
    expected_now = 0.0
    progress_ratio = 1.0
    if predicted_total > 20 and baseline_target > 0:
        expected_now = predicted_total * min(elapsed / baseline_target, 1.0)
        if expected_now > 15:
            progress_ratio = _clamp(actual_removed / expected_now, 0.35, 1.80)

    # Project the remaining time from measured progress. Confidence and outcome
    # samples determine how strongly the coach may move away from the baseline.
    feedback_samples = sum(int(r.get("outcome_feedback_samples", 0) or 0) for r in active)
    learning_weight = min(feedback_samples / 12.0, 1.0) * min(max(confidence / 100.0, 0.25), 0.95)

    if predicted_total > 20 and actual_removed > 10 and elapsed >= 2:
        observed_rate = actual_removed / elapsed
        remaining_moisture = max(predicted_total - actual_removed, 0.0)
        projected_remaining = remaining_moisture / max(observed_rate, 1.0)
        adaptive_target = elapsed + projected_remaining
    else:
        adaptive_target = baseline_target

    target = baseline_target * (1.0 - learning_weight) + adaptive_target * learning_weight
    target = _clamp(target, min_duration, max_duration)

    # Marginal benefit can shorten a session even when the initial target was
    # longer; conversely a useful next 5 min can justify a limited extension.
    min_return = _f(options.get("min_return_next_5_min_ml"), 25.0)
    health_urgent = any(
        _f(r.get("surface_rh")) >= _f(options.get("mould_critical_surface_rh"), 90.0)
        or (bool(r.get("co2_available", r.get("co2") is not None)) and _f(r.get("co2")) >= _f(options.get("co2_critical"), 1400.0))
        for r in active
    )

    state = "on_track"
    reason = "Ist-Verlauf entspricht dem gelernten Lüftungsmodell"

    if elapsed >= min_duration and next5 < min_return and not health_urgent:
        target = min(target, elapsed)
        state = "shortened"
        reason = f"Zusatznutzen fällt ab: interner 5-Minuten-Schließcheck nur noch etwa {round(next5)} ml"
    elif progress_ratio >= 1.18 and elapsed >= min_duration:
        target = min(target, max(elapsed, baseline_target - min(3.0, baseline_target * 0.22)))
        state = "shortened"
        reason = f"Lüftung wirkt schneller als erwartet ({round((progress_ratio-1)*100)} % voraus)"
    elif progress_ratio <= 0.78 and next5 >= min_return and elapsed < max_duration:
        extension = min(4.0, max_duration - baseline_target)
        target = max(target, baseline_target + extension * learning_weight)
        state = "extended"
        reason = f"Lüftung wirkt langsamer als erwartet; weitere Luftwechsel sind noch sinnvoll"

    target = _clamp(target, min_duration, max_duration)
    remaining = max(target - elapsed, 0.0)

    # If the learned target has been reached and marginal return is weak, ask to close.
    if (
        all_close_decisions_ready
        and elapsed >= min_duration
        and remaining <= 0.35
        and next5 < max(min_return * 1.25, 35.0)
        and not health_urgent
    ):
        out = dict(recommendation)
        out.update({
            "kind": "close", "status": "close_windows", "title": "Jetzt schließen",
            "instruction": " + ".join(str(r.get("name", r.get("key", "Raum"))) for r in active) + " schließen",
            "summary": "FreshAirIQ hat die laufende Lüftung neu bewertet; der effiziente Endpunkt ist erreicht.",
            "duration_min": 0.0, "estimated_removed_ml": round(actual_removed),
            "live_coach": True, "live_coach_state": "close",
            "live_coach_reason": reason, "live_coach_target_min": round(target, 1),
            "live_coach_remaining_min": 0.0, "live_coach_progress_ratio": round(progress_ratio, 2),
            "live_coach_next_5_min_ml": round(next5),
            "live_coach_next_5_min_temperature_c": round(next5_temp, 2),
            "live_coach_confidence": confidence,
        })
        reasons = list(out.get("reasons") or [])
        reasons.insert(0, reason)
        out["reasons"] = reasons[:6]
        return out

    out = dict(recommendation)
    names = " + ".join(str(r.get("name", r.get("key", "Raum"))) for r in active)
    out.update({
        "instruction": f"{names} offen lassen · noch ca. {max(round(remaining), 1)} min",
        "duration_min": round(remaining, 1),
        "estimated_removed_ml": round(next5),
        "live_coach": True, "live_coach_state": state,
        "live_coach_reason": reason, "live_coach_target_min": round(target, 1),
        "live_coach_baseline_target_min": round(baseline_target, 1),
        "live_coach_remaining_min": round(remaining, 1),
        "live_coach_progress_ratio": round(progress_ratio, 2),
        "live_coach_actual_removed_ml": round(actual_removed),
        "live_coach_expected_now_ml": round(expected_now),
        "live_coach_next_5_min_ml": round(next5),
        "live_coach_next_5_min_temperature_c": round(next5_temp, 2),
        "live_coach_confidence": confidence,
        "live_coach_feedback_samples": feedback_samples,
    })
    reasons = list(out.get("reasons") or [])
    reasons.insert(0, reason)
    out["reasons"] = reasons[:6]
    return out
