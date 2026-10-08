"""FreshAirIQ predictive moisture and behaviour anticipation layer.

Uses only learned room routines plus current physical room state. It never invents
an event from clock time alone: a future event requires learned bucket maturity,
a plausible projected rise, and a useful ventilation opportunity.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from math import isfinite

from .routines import project_generation_ml


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _future_rh(room: dict[str, Any], generated_ml: float) -> float:
    """Approximate future RH at unchanged temperature from projected water mass."""
    current_rh = _f(room.get("humidity"))
    current_ah = _f(room.get("absolute_humidity"))
    volume = max(_f(room.get("volume_m3")), 1.0)
    if current_rh <= 0 or current_ah <= 0:
        return current_rh
    future_ah = current_ah + max(generated_ml, 0.0) / volume
    return _clamp(current_rh * future_ah / current_ah, 0.0, 100.0)


def predict_room_event(
    room: dict[str, Any],
    options: dict[str, Any],
    now: datetime,
    *,
    horizons: tuple[int, ...] = (15, 30, 60, 120),
) -> dict[str, Any] | None:
    """Return the earliest meaningful learned moisture event for one room."""
    if room.get("data_quality") != "ok" or not room.get("calculation_enabled", True):
        return None
    if room.get("active"):
        return None

    start_rh = _f(options.get("start_rh"), 62.0)
    high_rh = _f(options.get("high_rh"), 68.0)
    current_rh = _f(room.get("humidity"))
    current_rate = max(_f(room.get("routine_expected_source_ml_min"),
                          room.get("forecast_source_rate_ml_min")), 0.0)
    potential = max(_f(room.get("realistic_potential_ml", room.get("potential_ml"))), 0.0)
    min_room_potential = max(_f(options.get("min_potential_room_ml"), 100.0), 60.0)

    prior_generation = 0.0
    prior_horizon = 0
    best = None

    for horizon in horizons:
        generated, maturity = project_generation_ml([room], now, horizon)
        if maturity < 18.0:
            prior_generation, prior_horizon = generated, horizon
            continue

        future_rh = _future_rh(room, generated)
        segment_min = max(horizon - prior_horizon, 1)
        segment_generation = max(generated - prior_generation, 0.0)
        future_segment_rate = segment_generation / segment_min

        # A "routine event" requires either an approaching humidity threshold
        # or a learned future source rate clearly above the current baseline.
        threshold_crossing = current_rh < start_rh and future_rh >= start_rh
        high_crossing = current_rh < high_rh and future_rh >= high_rh
        baseline = max(current_rate, 0.35)
        rate_spike = future_segment_rate >= max(baseline * 1.55, baseline + 0.8)

        if not (threshold_crossing or high_crossing or rate_spike):
            prior_generation, prior_horizon = generated, horizon
            continue

        confidence = 30.0 + maturity * 0.55
        if threshold_crossing:
            confidence += 8.0
        if high_crossing:
            confidence += 12.0
        if rate_spike:
            confidence += min((future_segment_rate - baseline) * 5.0, 12.0)
        confidence = _clamp(confidence, 0.0, 96.0)

        # Pre-ventilation is only actionable when the room already has useful
        # removable moisture. Otherwise IQ should observe rather than recommend.
        pre_vent_useful = potential >= min_room_potential * 0.60 and _f(room.get("delta_g_m3")) > 0

        candidate = {
            "room_key": str(room.get("key") or ""),
            "room_name": str(room.get("name", room.get("key", "Raum"))),
            "horizon_min": horizon,
            "projected_generation_ml": round(generated),
            "projected_rh": round(future_rh, 1),
            "current_rh": round(current_rh, 1),
            "routine_maturity": round(maturity, 1),
            "confidence": round(confidence),
            "segment_rate_ml_min": round(future_segment_rate, 2),
            "current_rate_ml_min": round(current_rate, 2),
            "threshold_crossing": threshold_crossing,
            "high_crossing": high_crossing,
            "rate_spike": rate_spike,
            "pre_vent_useful": pre_vent_useful,
            "current_potential_ml": round(potential),
        }
        best = candidate
        break

    return best


def build_anticipation_state(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    events = [
        event for room in rooms.values()
        if (event := predict_room_event(room, options, now)) is not None
    ]
    events.sort(key=lambda x: (int(x["horizon_min"]), -int(x["confidence"])))
    if not events:
        return {
            "active": False, "events": [], "confidence": 0,
            "summary": "Keine ausreichend sichere bevorstehende Feuchteentwicklung gelernt.",
        }
    primary = events[0]
    return {
        "active": True,
        "events": events[:5],
        "primary": primary,
        "confidence": int(primary["confidence"]),
        "summary": (
            f"{primary['room_name']}: gelernter Feuchteanstieg in etwa "
            f"{primary['horizon_min']} min erwartet"
        ),
    }


def refine_with_anticipation(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Enrich or cautiously pre-empt the current recommendation."""
    state = build_anticipation_state(rooms, options, now)
    out = dict(recommendation)
    out["anticipation"] = state
    out["anticipation_engine"] = "v1"

    if not state.get("active"):
        return out

    primary = state["primary"]
    kind = str(out.get("kind") or "okay")
    locked = kind in {"close", "continue", "sensor", "ventilate", "pollen_wait"}
    if locked:
        return out

    # Below this confidence we show the prediction only as IQ observation.
    if int(primary.get("confidence", 0)) < 55:
        return out

    room = rooms.get(str(primary["room_key"]))
    if not room:
        return out

    reasons = list(out.get("reasons") or [])
    event_reason = (
        f"{primary['room_name']}: aus gelernten Routinen werden in "
        f"{primary['horizon_min']} min etwa +{primary['projected_generation_ml']} ml erwartet"
    )

    # Only pre-ventilate if it is already physically useful. Otherwise leave the
    # recommendation non-actionable and simply expose the anticipated event.
    if primary.get("pre_vent_useful") and int(primary["horizon_min"]) <= 60:
        duration = max(_f(options.get("min_duration_min"), 3.0), 3.0)
        removed = max(_f(room.get("realistic_potential_ml", room.get("potential_ml"))), 0.0)
        out.update({
            "kind": "prepare",
            "status": "prepare",
            "title": "Vorausschauend handeln",
            "instruction": f"{primary['room_name']} jetzt kurz vorlüften",
            "summary": (
                f"FreshAirIQ erwartet in etwa {primary['horizon_min']} min einen "
                f"typischen Feuchteanstieg und schafft vorher Puffer."
            ),
            "room_keys": [str(primary["room_key"])],
            "duration_min": round(duration, 1),
            "estimated_removed_ml": round(removed),
            "forecast_confidence": int(primary["confidence"]),
            "severity": "attention",
            "anticipatory_action": True,
        })
        reasons.insert(0, event_reason)
        reasons.insert(1, f"Vorlüften ist aktuell physikalisch sinnvoll ({round(removed)} ml entfernbar)")
        out["reasons"] = reasons[:6]
    else:
        reasons.insert(0, event_reason)
        out["reasons"] = reasons[:6]
        out["anticipatory_observation"] = True

    return out
