"""Conservative passive-ventilation detection for FreshAirIQ.

A closed room is never called passively ventilated merely because another
window is open. Detection requires a plausible airflow connection and a
multi-sample absolute-humidity trend toward the reference that existed when
the observation started. The estimate remains display-only and is never added
to the measured house live balance.
"""
from __future__ import annotations

from typing import Any


def evaluate_passive_ventilation(
    *,
    start_ah: float,
    current_ah: float,
    reference_ah: float,
    volume_m3: float,
    elapsed_min: float,
    connected: bool,
    start_reference_ah: float | None = None,
    samples: list[dict[str, float]] | None = None,
    connection_strength: float = 1.0,
) -> dict[str, Any]:
    """Return a conservative estimate for a closed, indirectly aired room."""
    volume = max(float(volume_m3), 0.0)
    elapsed = max(float(elapsed_min), 0.0)
    strength = min(max(float(connection_strength), 0.0), 1.0)
    if not connected or strength < 0.45 or volume <= 0.0:
        return {"active": False, "estimated_ml": 0.0, "confidence": 0, "reason": "not_connected"}

    start = float(start_ah)
    current = float(current_ah)
    reference_start = float(start_reference_ah if start_reference_ah is not None else reference_ah)
    reference_now = float(reference_ah)
    expected_delta = reference_start - start
    observed_delta = current - start
    estimated_ml = (start - current) * volume

    min_effect_ml = max(3.0, volume * (0.04 if strength < 0.8 else 0.03))
    if elapsed < 4.0:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "warming_up"}
    if abs(expected_delta) < 0.25:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "reference_too_similar"}
    # If the current reference has crossed to the opposite side of the start
    # value, the original airflow hypothesis is no longer stable enough.
    if (reference_now - start) * expected_delta <= 0.0:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "reference_changed_direction"}
    if abs(estimated_ml) < min_effect_ml:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "below_noise_floor"}
    if observed_delta * expected_delta <= 0.0:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "wrong_direction"}

    rows = []
    for row in samples or []:
        try:
            rows.append((float(row["elapsed_min"]), float(row["ah"])))
        except (KeyError, TypeError, ValueError):
            continue
    # Ensure the true start baseline and current sample participate in the trend.
    rows.append((0.0, start))
    rows.append((elapsed, current))
    rows = sorted({(round(t, 3), round(v, 5)) for t, v in rows})
    if len(rows) < 3:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "too_few_samples"}

    direction = 1.0 if expected_delta > 0.0 else -1.0
    projected = [direction * (ah - start) for _, ah in rows]
    forward_steps = sum(1 for a, b in zip(projected, projected[1:]) if b >= a - 0.015)
    regressions = sum(1 for a, b in zip(projected, projected[1:]) if b < a - 0.04)
    monotonic_ratio = forward_steps / max(len(projected) - 1, 1)
    total_progress = projected[-1]
    if total_progress <= 0.0 or regressions > 1 or monotonic_ratio < 0.66:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": 0, "reason": "trend_not_stable"}

    progress = min(abs(observed_delta) / max(abs(expected_delta), 0.25), 1.0)
    sample_bonus = min(max(len(rows) - 3, 0), 5) * 4.0
    confidence = 25.0 + min(elapsed, 20.0) * 1.2 + progress * 25.0 + sample_bonus + strength * 15.0
    if strength < 0.8:
        confidence -= 8.0
    confidence = round(min(max(confidence, 0.0), 90.0))
    if confidence < 45:
        return {"active": False, "estimated_ml": round(estimated_ml, 1), "confidence": int(confidence), "reason": "confidence_too_low"}
    return {
        "active": True,
        "estimated_ml": round(estimated_ml, 1),
        "confidence": int(confidence),
        "reason": "stable_sensor_trend_toward_start_reference",
    }


def learn_passive_exchange(
    *,
    old_rate: float,
    old_samples: int,
    start_ah: float,
    current_ah: float,
    start_reference_ah: float,
    elapsed_min: float,
) -> dict[str, Any]:
    """Learn one conservative indirect-air-exchange observation.

    This model is deliberately independent from direct opening learning.  It
    uses only the fraction of the original room/reference AH gradient that was
    measurably traversed during a validated passive observation.
    """
    elapsed = max(float(elapsed_min), 0.0)
    gradient = abs(float(start_ah) - float(start_reference_ah))
    progress = abs(float(current_ah) - float(start_ah))
    rate = min(max(float(old_rate), 0.002), 0.25)
    samples = min(max(int(old_samples), 0), 1000)
    if elapsed < 5.0 or gradient < 0.25 or progress <= 0.0:
        return {"valid": False, "rate": rate, "samples": samples, "observed_rate": None}
    fraction = min(max(progress / gradient, 0.0), 0.85)
    observed = min(max(fraction / elapsed, 0.002), 0.25)
    alpha = 0.20 if samples < 5 else 0.10
    learned = rate * (1.0 - alpha) + observed * alpha
    return {
        "valid": True,
        "rate": round(min(max(learned, 0.002), 0.25), 6),
        "samples": min(samples + 1, 1000),
        "observed_rate": round(observed, 6),
    }
