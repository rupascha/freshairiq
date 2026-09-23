"""FreshAirIQ Language Confidence Layer.

Adapts only the wording of an already-final recommendation to the evidence
maturity and confidence of the current situation.  It must never change the
physical action, rooms, duration, forecast values or safety thresholds.
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


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _band(maturity: float) -> tuple[str, str]:
    if maturity < 12:
        return "grundmodell", "Grundmodell"
    if maturity < 28:
        return "beobachtet", "Beobachtet"
    if maturity < 45:
        return "muster_erkannt", "Muster erkannt"
    if maturity < 62:
        return "bestaetigt", "Bestätigt"
    if maturity < 78:
        return "eingelernt", "Eingelernt"
    if maturity < 92:
        return "sehr_gut_eingelernt", "Sehr gut eingelernt"
    return "auf_beduerfnisse_optimiert", "Auf deine Bedürfnisse optimiert"


def _relevant_maturity(kind: str, selected: list[dict[str, Any]]) -> tuple[float, int]:
    """Evidence maturity for the models that actually support this wording."""
    if not selected:
        return 0.0, 0
    scores: list[float] = []
    samples = 0
    for room in selected:
        physics_n = int(_f(room.get("learning_samples")))
        live_n = int(_f(room.get("forecast_observation_samples")))
        feedback_n = int(_f(room.get("outcome_feedback_samples")))
        strategy_n = int(_f(room.get("strategy_samples")))
        behaviour_n = int(_f(room.get("behaviour_recommendation_opportunities"))) + int(_f(room.get("behaviour_duration_samples")))
        if kind in {"continue", "close"}:
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(live_n / 60.0, 1.0), min(feedback_n / 80.0, 1.0)])
            samples += physics_n + live_n + feedback_n
        elif kind == "ventilate":
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(feedback_n / 80.0, 1.0), min(strategy_n / 100.0, 1.0), min(behaviour_n / 100.0, 1.0)])
            samples += physics_n + feedback_n + strategy_n + behaviour_n
        else:
            score = 100.0 * _avg([min(physics_n / 80.0, 1.0), min(feedback_n / 80.0, 1.0)])
            samples += physics_n + feedback_n
        scores.append(score)
    return _clamp(_avg(scores)), samples


def _situation_confidence(recommendation: dict[str, Any], selected: list[dict[str, Any]]) -> float:
    brain = recommendation.get("decision_brain") if isinstance(recommendation.get("decision_brain"), dict) else {}
    impact = brain.get("impact") if isinstance(brain.get("impact"), dict) else {}
    base = _f(impact.get("confidence"), _f(recommendation.get("confidence"), 50.0))
    room_conf = [_f(r.get("forecast_confidence")) for r in selected if r.get("forecast_confidence") is not None]
    if room_conf:
        base = 0.6 * base + 0.4 * _avg(room_conf)
    # Measurement coherence is a real-time property and therefore belongs to
    # situation confidence, not model maturity.
    quality_factor = {"excellent": 1.0, "acceptable": 0.92, "held": 0.60, "uncertain": 0.72, "stale": 0.45, "invalid": 0.35}
    factors = []
    for room in selected:
        q = str(room.get("measurement_frame_quality") or "").lower()
        if q:
            factors.append(quality_factor.get(q, 0.85))
    if factors:
        base *= _avg(factors)
    return _clamp(base)


def adapt_language_confidence(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    store_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a presentation-only copy whose wording reflects evidence depth."""
    out = dict(recommendation or {})
    brain = dict(out.get("decision_brain") or {})
    kind = str(out.get("kind") or "okay")
    room_keys = [str(k) for k in (out.get("room_keys") or [])]
    selected = [rooms[k] for k in room_keys if k in rooms]
    # House presentation may intentionally have no room chips. In that case the
    # canonical recommendation still carries room_keys; if not, use active rooms.
    if not selected and str(out.get("presentation_scope")) == "house":
        selected = [r for r in rooms.values() if isinstance(r, dict) and r.get("active")]

    maturity, evidence_samples = _relevant_maturity(kind, selected)
    store = store_data or {}
    # If the final recommendation is explicitly driven by a night or house
    # strategy, include that model's own evidence depth instead of pretending
    # the room model alone supports the wording.
    ns = brain.get("night_strategy") if isinstance(brain.get("night_strategy"), dict) else {}
    if brain.get("night_strategy_primary") or (ns.get("active") and kind in {"okay", "wait"}):
        night_n = int(_f(store.get("night_model_samples")))
        maturity = _avg([maturity, min(night_n / 120.0, 1.0) * 100.0]) if selected else min(night_n / 120.0, 1.0) * 100.0
        evidence_samples += night_n
    if str(out.get("presentation_scope")) == "house":
        house_n = int(_f(store.get("house_strategy_samples")))
        maturity = _avg([maturity, min(house_n / 150.0, 1.0) * 100.0])
        evidence_samples += house_n
    situation = _situation_confidence(out, selected)
    band_key, band_label = _band(maturity)
    original_summary = str(brain.get("summary") or out.get("summary") or "").strip()

    # Evidence-calibrated voice.  The layer intentionally avoids claims such as
    # "normally" or "comparable conditions" until the data depth supports them.
    if band_key == "grundmodell":
        lead = "FreshAirIQ arbeitet hier noch überwiegend mit Gebäudephysik und aktuellen Messdaten."
    elif band_key == "beobachtet":
        lead = "FreshAirIQ sammelt erste Erfahrungen, verändert das persönliche Modell aber noch bewusst vorsichtig."
    elif band_key == "muster_erkannt":
        lead = "FreshAirIQ erkennt wiederkehrende Muster, wartet aber auf weitere unabhängige Bestätigungen."
    elif band_key == "bestaetigt":
        lead = "Mehrere unabhängige Beobachtungen bestätigen das erkannte Lüftungsverhalten dieser Räume."
    elif band_key == "eingelernt":
        lead = "FreshAirIQ hat für diese Räume eine belastbare eigene Datenbasis und darf das Grundmodell vorsichtig personalisieren."
    elif band_key == "sehr_gut_eingelernt":
        lead = "FreshAirIQ kennt das Lüftungsverhalten dieser Räume inzwischen sehr gut und validiert seine Anpassungen fortlaufend an der Realität."
    else:
        lead = "FreshAirIQ kennt hier nicht nur das Raumverhalten sehr gut, sondern kann die Empfehlung zusätzlich an bestätigte Nutzungs- und Komfortmuster anpassen."

    if situation < 45:
        qualifier = " Die aktuelle Situation ist jedoch ungewöhnlich oder messtechnisch unsicher, deshalb bleibt die Einschätzung bewusst vorsichtig."
    elif situation < 65:
        qualifier = " Für die aktuelle Situation ist die Sicherheit noch begrenzt, deshalb ist die Formulierung bewusst zurückhaltend."
    elif situation >= 85 and maturity >= 60:
        qualifier = " Auch die aktuelle Situation lässt sich mit hoher Sicherheit bewerten."
    else:
        qualifier = ""

    # Do not drown out urgent live/close instructions. Put learning context after
    # the action summary there; for idle/start recommendations it can lead.
    confidence_text = (lead + qualifier).strip()
    if kind in {"continue", "close"}:
        summary = (original_summary + " " + confidence_text).strip()
    else:
        summary = (confidence_text + " " + original_summary).strip()

    reasons = list(brain.get("why") or out.get("reasons") or [])
    # Surface the strongest already-learned personal signal. This changes only
    # wording/reason priority, never the selected action or physical thresholds.
    personal_traces: list[tuple[float, str]] = []
    for room in selected:
        name = str(room.get("name") or "Dieser Raum")
        routine_maturity = _f(room.get("routine_maturity"))
        routine_samples = int(_f(room.get("routine_source_samples")))
        routine_rate = room.get("routine_expected_source_ml_min")
        if routine_samples >= 8 and routine_maturity >= 25 and routine_rate is not None:
            hourly = _f(routine_rate) * 60.0
            if abs(hourly) >= 10:
                direction = "Feuchtezunahme" if hourly > 0 else "Feuchteabnahme"
                personal_traces.append((routine_maturity, f"Persönliches Muster: {name} zeigt um diese Zeit häufig eine {direction} von etwa {abs(hourly):.0f} ml/h"))
        strategy_samples = int(_f(room.get("strategy_samples")))
        success = _f(room.get("outcome_success_rate"))
        feedback = int(_f(room.get("outcome_feedback_samples")))
        if strategy_samples >= 10 and feedback >= 5 and success > 0:
            personal_traces.append((min(100.0, strategy_samples / 2.0), f"Gelernte Erfahrung: {name} · {feedback} überprüfte Ergebnisse · Prognosetreffer {success:.0f} %"))
    if personal_traces:
        personal_traces.sort(key=lambda item: item[0], reverse=True)
        trace_text = personal_traces[0][1]
        if trace_text not in reasons:
            reasons.insert(0, trace_text)
    # One compact, factual trace makes the change visible without turning the
    # recommendation into a diagnostics panel.
    trace = f"Lernstand: {band_label} ({maturity:.0f} %) · Situationssicherheit {situation:.0f} %"
    if trace not in reasons:
        reasons.append(trace)
    reasons = reasons[:7]

    brain["summary"] = summary
    brain["why"] = reasons
    brain["language_confidence"] = {
        "version": "v1",
        "maturity_percent": round(maturity, 1),
        "maturity_band": band_key,
        "maturity_label": band_label,
        "evidence_samples": evidence_samples,
        "situation_confidence_percent": round(situation, 1),
        "calibrated_wording": True,
    }
    out["summary"] = summary
    out["reasons"] = reasons
    out["decision_brain"] = brain
    out["language_confidence"] = dict(brain["language_confidence"])
    return out
