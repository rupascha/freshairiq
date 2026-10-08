"""FreshAirIQ Learning 3.0 shadow-model validation.

The production moisture calibration is intentionally not nudged after every
single session. Alternative multipliers compete in the background against the
currently active forecast. Only repeated, comparable real-world evidence may
promote a shadow candidate. A promoted factor is then guarded by a short
counterfactual rollback window.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

_SHADOW_MULTIPLIERS = (0.85, 0.925, 1.0, 1.075, 1.15)
_MIN_PROMOTION_SAMPLES = 8
_MIN_IMPROVEMENT = 0.12
_MIN_WIN_RATE = 0.65
_ROLLBACK_SAMPLES = 5
_ROLLBACK_IMPROVEMENT = 0.10


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None



def _safe_int(value: Any, default: int = 0, *, low: int = 0, high: int = 1_000_000) -> int:
    """Return a bounded integer for potentially corrupt persisted counters."""
    number = _finite(value)
    if number is None:
        return default
    return min(max(int(number), low), high)


def _safe_nonnegative(value: Any) -> float:
    number = _finite(value)
    return max(number, 0.0) if number is not None else 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def ensure_shadow_defaults(room: dict[str, Any]) -> None:
    room.setdefault("shadow_learning_generation", 1)
    room.setdefault("shadow_learning_samples", 0)
    room.setdefault("shadow_learning_total_samples", 0)
    room.setdefault("shadow_learning_candidates", {})
    room.setdefault("shadow_learning_status", "Beobachtet Produktionsmodell")
    room.setdefault("shadow_learning_last_action", "observing")
    room.setdefault("shadow_learning_last_improvement_pct", None)
    room.setdefault("shadow_learning_last_multiplier", None)
    room.setdefault("shadow_learning_promotions", 0)
    room.setdefault("shadow_learning_rollbacks", 0)
    room.setdefault("shadow_learning_cooldown", 0)
    room.setdefault("shadow_rollback_active", False)
    room.setdefault("shadow_rollback_previous_factor", None)
    room.setdefault("shadow_rollback_promoted_factor", None)
    room.setdefault("shadow_rollback_samples", 0)
    room.setdefault("shadow_rollback_active_error", 0.0)
    room.setdefault("shadow_rollback_previous_error", 0.0)
    room.setdefault("shadow_rollback_previous_wins", 0)


def _reset_competition(room: dict[str, Any], *, cooldown: int = 0) -> None:
    room["shadow_learning_samples"] = 0
    room["shadow_learning_candidates"] = {}
    room["shadow_learning_cooldown"] = _safe_int(cooldown)
    room["shadow_learning_generation"] = min(_safe_int(room.get("shadow_learning_generation", 1), 1, low=1, high=100000) + 1, 100000)


def _update_rollback(room: dict[str, Any], predicted: float, actual: float) -> dict[str, Any] | None:
    if not bool(room.get("shadow_rollback_active")):
        return None
    previous = _finite(room.get("shadow_rollback_previous_factor"))
    promoted = _finite(room.get("shadow_rollback_promoted_factor"))
    if previous is None or promoted is None or promoted <= 0:
        room["shadow_rollback_active"] = False
        return None

    # Promotion only occurs after outcome-feedback maturity reaches full weight,
    # so factor ratios are a valid counterfactual for the guarded window.
    previous_prediction = predicted * previous / promoted
    active_error = abs(actual - predicted)
    previous_error = abs(actual - previous_prediction)
    room["shadow_rollback_active_error"] = _safe_nonnegative(room.get("shadow_rollback_active_error")) + active_error
    room["shadow_rollback_previous_error"] = _safe_nonnegative(room.get("shadow_rollback_previous_error")) + previous_error
    if previous_error + 1e-9 < active_error:
        room["shadow_rollback_previous_wins"] = min(_safe_int(room.get("shadow_rollback_previous_wins")) + 1, 1_000_000)
    samples = min(_safe_int(room.get("shadow_rollback_samples")) + 1, 1_000_000)
    room["shadow_rollback_samples"] = samples
    if samples < _ROLLBACK_SAMPLES:
        return {"action": "guarding_promotion", "samples": samples}

    active_total = max(_safe_nonnegative(room.get("shadow_rollback_active_error")), 1e-9)
    previous_total = _safe_nonnegative(room.get("shadow_rollback_previous_error"))
    improvement = (active_total - previous_total) / active_total
    wins = _safe_int(room.get("shadow_rollback_previous_wins"))
    should_rollback = improvement >= _ROLLBACK_IMPROVEMENT and wins >= 3
    room["shadow_rollback_active"] = False
    if should_rollback:
        room["outcome_removed_factor"] = round(_clamp(previous, 0.55, 1.55), 3)
        room["shadow_learning_rollbacks"] = min(_safe_int(room.get("shadow_learning_rollbacks"), high=1000) + 1, 1000)
        room["shadow_learning_last_action"] = "rollback"
        room["shadow_learning_status"] = "Letzte Anpassung automatisch zurückgenommen"
        room["shadow_learning_last_improvement_pct"] = round(improvement * 100.0, 1)
        _reset_competition(room, cooldown=4)
        return {"action": "rollback", "factor": room["outcome_removed_factor"], "improvement": improvement}

    room["shadow_learning_last_action"] = "promotion_confirmed"
    room["shadow_learning_status"] = "Neue Anpassung durch Realmessungen bestätigt"
    _reset_competition(room, cooldown=2)
    return {"action": "promotion_confirmed", "improvement": -improvement}


def process_shadow_feedback(room: dict[str, Any], *, predicted_removed_ml: float, actual_removed_ml: float) -> dict[str, Any]:
    """Score shadow candidates and promote only a statistically repeated winner."""
    ensure_shadow_defaults(room)
    predicted = _finite(predicted_removed_ml)
    actual = _finite(actual_removed_ml)
    if predicted is None or actual is None or predicted < 20.0:
        return {"action": "skipped", "reason": "invalid_sample"}

    rollback = _update_rollback(room, predicted, actual)
    if rollback is not None:
        return rollback

    cooldown = _safe_int(room.get("shadow_learning_cooldown"))
    if cooldown > 0:
        room["shadow_learning_cooldown"] = cooldown - 1
        room["shadow_learning_status"] = "Beobachtet nach letzter Modellentscheidung"
        return rollback or {"action": "cooldown"}

    candidates = room.get("shadow_learning_candidates")
    if not isinstance(candidates, dict):
        candidates = {}
        room["shadow_learning_candidates"] = candidates

    baseline_error = abs(actual - predicted)
    for multiplier in _SHADOW_MULTIPLIERS:
        key = f"{multiplier:.3f}"
        row = candidates.get(key)
        if not isinstance(row, dict):
            row = {"samples": 0, "abs_error": 0.0, "sq_error": 0.0, "wins": 0}
            candidates[key] = row
        candidate_error = abs(actual - predicted * multiplier)
        row["samples"] = min(_safe_int(row.get("samples"), high=100000) + 1, 100000)
        row["abs_error"] = round(_safe_nonnegative(row.get("abs_error")) + candidate_error, 4)
        row["sq_error"] = round(_safe_nonnegative(row.get("sq_error")) + candidate_error * candidate_error, 4)
        if candidate_error + 1e-9 < baseline_error:
            row["wins"] = min(_safe_int(row.get("wins"), high=100000) + 1, 100000)

    samples = min(_safe_int(room.get("shadow_learning_samples"), high=100000) + 1, 100000)
    room["shadow_learning_samples"] = samples
    room["shadow_learning_total_samples"] = min(_safe_int(room.get("shadow_learning_total_samples")) + 1, 1000000)
    room["shadow_learning_status"] = f"Shadow-Modelle vergleichen reale Ergebnisse · {samples}/{_MIN_PROMOTION_SAMPLES} Mindestproben"
    room["shadow_learning_last_action"] = "observing"

    if samples < _MIN_PROMOTION_SAMPLES or _safe_int(room.get("outcome_feedback_samples")) < 7:
        return rollback or {"action": "observing", "samples": samples}

    baseline = candidates.get("1.000") or {}
    baseline_mae = _safe_nonnegative(baseline.get("abs_error")) / max(_safe_int(baseline.get("samples")), 1)
    if baseline_mae < 5.0:
        room["shadow_learning_status"] = "Produktionsmodell bereits sehr genau · keine Anpassung nötig"
        _reset_competition(room, cooldown=2)
        return {"action": "baseline_good"}

    allowed_keys = [f"{multiplier:.3f}" for multiplier in _SHADOW_MULTIPLIERS]
    winner_key = min(
        allowed_keys,
        key=lambda key: (
            _finite((candidates.get(key) or {}).get("abs_error"))
            if isinstance(candidates.get(key), dict) and _finite((candidates.get(key) or {}).get("abs_error")) is not None
            else 1e99
        ),
    )
    winner = candidates[winner_key]
    multiplier = float(winner_key)
    winner_mae = _safe_nonnegative(winner.get("abs_error")) / max(_safe_int(winner.get("samples")), 1)
    improvement = (baseline_mae - winner_mae) / max(baseline_mae, 1e-9)
    win_rate = _safe_int(winner.get("wins")) / max(_safe_int(winner.get("samples")), 1)
    if multiplier == 1.0 or improvement < _MIN_IMPROVEMENT or win_rate < _MIN_WIN_RATE:
        if samples >= 16:
            _reset_competition(room)
        room["shadow_learning_last_improvement_pct"] = round(max(improvement, 0.0) * 100.0, 1)
        return {"action": "no_promotion", "improvement": improvement, "win_rate": win_rate}

    old_factor = _clamp(_finite(room.get("outcome_removed_factor")) or 1.0, 0.55, 1.55)
    # Never make a large jump. Shadow evidence chooses direction/magnitude, but
    # production moves by at most 8% per promotion.
    bounded_multiplier = _clamp(multiplier, 0.92, 1.08)
    new_factor = round(_clamp(old_factor * bounded_multiplier, 0.55, 1.55), 3)
    if abs(new_factor - old_factor) < 0.005:
        _reset_competition(room, cooldown=2)
        return {"action": "no_change"}

    room["outcome_removed_factor"] = new_factor
    room["shadow_learning_promotions"] = min(_safe_int(room.get("shadow_learning_promotions"), high=1000) + 1, 1000)
    room["shadow_learning_last_action"] = "promoted"
    room["shadow_learning_status"] = "Shadow-Modell nach wiederholtem Realvergleich übernommen · Rollback-Schutz aktiv"
    room["shadow_learning_last_improvement_pct"] = round(improvement * 100.0, 1)
    room["shadow_learning_last_multiplier"] = round(multiplier, 3)
    room["shadow_rollback_active"] = True
    room["shadow_rollback_previous_factor"] = old_factor
    room["shadow_rollback_promoted_factor"] = new_factor
    room["shadow_rollback_samples"] = 0
    room["shadow_rollback_active_error"] = 0.0
    room["shadow_rollback_previous_error"] = 0.0
    room["shadow_rollback_previous_wins"] = 0
    _reset_competition(room)
    return {
        "action": "promoted", "old_factor": old_factor, "new_factor": new_factor,
        "improvement": improvement, "win_rate": win_rate, "multiplier": multiplier,
    }
