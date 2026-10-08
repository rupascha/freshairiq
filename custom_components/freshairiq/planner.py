"""FreshAirIQ multi-hour day/night planning engine.

Builds a conservative plan across several hours using the configured weather
forecast, learned room routines and the existing physical room model. The
planner does not replace real-time health/safety decisions.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any

from .routines import project_generation_ml


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _pressure(room: dict[str, Any], options: dict[str, Any]) -> float:
    rh = _f(room.get("humidity"))
    surf = _f(room.get("surface_rh"))
    co2_available = bool(room.get("co2_available", room.get("co2") is not None))
    co2 = _f(room.get("co2")) if co2_available else 0.0
    high = _f(options.get("high_rh"), 68.0)
    mould = _f(options.get("mould_warn_surface_rh"), 80.0)
    co2_warn = _f(options.get("co2_warn"), 1000.0)
    p = max((rh-high)*4.0, 0.0) + max((surf-mould)*5.0, 0.0)
    if co2_available and co2 >= co2_warn:
        p += 30.0 + min((co2-co2_warn)/20.0, 30.0)
    return _clamp(p, 0.0, 100.0)


def build_multi_hour_plan(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    now: datetime,
    *,
    future_outdoor: dict[int, dict[str, Any]] | None = None,
    night_forecast_ml: float = 0.0,
    night_confidence: float = 0.0,
    horizon_hours: float = 8.0,
) -> dict[str, Any]:
    valid = [r for r in rooms.values()
             if r.get("calculation_enabled", True) and r.get("data_quality") == "ok"]
    closed = [r for r in valid if not r.get("active")]
    if not closed:
        return {"active": False, "horizon_hours": horizon_hours, "options": [], "reason": "Keine geschlossenen Räume planbar"}

    horizon_min = int(_clamp(horizon_hours * 60.0, 120.0, 720.0))
    boundaries = future_outdoor or {}
    delays = sorted(d for d in boundaries if 0 < int(d) <= horizon_min)
    # Keep a compact planning matrix. Hourly points are enough for multi-hour planning.
    delays = [d for d in delays if d <= 60 or d % 60 == 0][:10]

    current_potential = sum(max(_f(r.get("realistic_potential_ml", r.get("potential_ml"))), 0.0) for r in closed)

    # Hotfix 0.17.0.2: projected indoor moisture generation is not automatically
    # 100 % removable during the next ventilation window.  Convert generated
    # moisture into *ventilation-effective* potential using the same learned
    # current exchange fraction represented by realistic/theoretical potential.
    # This prevents multi-hour plans from inflating e.g. a few hundred ml of
    # current opportunity into multi-litre "removable" forecasts.
    theoretical_current = sum(max(_f(r.get("potential_ml")), 0.0) for r in closed)
    if theoretical_current > 1.0:
        ventilation_capture = _clamp(current_potential / theoretical_current, 0.02, 0.85)
    else:
        ventilation_capture = 0.12

    current_delta = max((_f(r.get("delta_g_m3")) for r in closed), default=0.0)
    pressure = max((_pressure(r, options) for r in closed), default=0.0)
    threshold = max(_f(options.get("min_potential_total_ml"), 500.0), 120.0)
    routine_total, routine_maturity = project_generation_ml(closed, now, horizon_min)

    candidates: list[dict[str, Any]] = []

    def add_candidate(cid: str, label: str, delay: int, ah: float | None, temp: float | None,
                      weather_conf: float, source: str) -> None:
        generation, maturity = project_generation_ml(closed, now, delay) if delay > 0 else (0.0, routine_maturity)
        if ah is None:
            # Current room delta is the fallback opportunity signal.
            dryness = max(current_delta, 0.0)
        else:
            dryness_values = [max(_f(r.get("absolute_humidity")) - ah, 0.0) for r in closed]
            dryness = sum(dryness_values) / max(len(dryness_values), 1)
        future_potential = max(current_potential + generation * ventilation_capture, 0.0)
        benefit = min(future_potential / threshold * 30.0, 58.0) + min(dryness * 5.0, 25.0)
        wait_risk = pressure * (delay / max(horizon_min, 60)) * 1.15
        generation_risk = min(generation / threshold * 13.0 * min(max(maturity/55.0, .2), 1.0), 30.0)
        thermal = 0.0
        if temp is not None:
            indoor = sum(_f(r.get("temperature")) * max(_f(r.get("volume_m3")),1) for r in closed) / max(sum(max(_f(r.get("volume_m3")),1) for r in closed),1)
            thermal = max(indoor-temp, 0.0) * 1.4
        score = benefit - wait_risk - generation_risk - min(thermal, 22.0)
        if delay == 0:
            score += pressure * .45
        confidence = _clamp(min(weather_conf, 95.0) * .55 + max(maturity, 20.0) * .30 + 15.0, 20.0, 95.0)
        candidates.append({
            "id": cid, "label": label, "delay_min": delay, "score": round(score,1),
            "projected_generation_ml": round(generation), "projected_potential_ml": round(future_potential),
            "ventilation_capture_fraction": round(ventilation_capture, 3),
            "dryness_g_m3": round(dryness,2), "temperature_c": round(temp,1) if temp is not None else None,
            "routine_maturity": round(maturity), "confidence": round(confidence),
            "source": source,
        })

    add_candidate("now", "Jetzt", 0, None, None, 85.0, "current")

    for delay in delays:
        b = boundaries[delay]
        add_candidate(
            f"in_{delay}", f"In {delay//60} h" if delay >= 60 and delay % 60 == 0 else f"In {delay} min",
            int(delay), _f(b.get("absolute_humidity"), None) if b.get("absolute_humidity") is not None else None,
            _f(b.get("temperature_c"), None) if b.get("temperature_c") is not None else None,
            _f(b.get("confidence"), 70.0), str(b.get("source") or "weather"),
        )

    # "Wait until morning/night end" remains a distinct strategy because it includes
    # the established overnight moisture model, not just one weather boundary.
    if night_forecast_ml > 0:
        night_score = 15.0 - pressure * .95 - min(night_forecast_ml / max(threshold,1) * 25.0, 38.0)
        candidates.append({
            "id": "after_night", "label": "Bis nach der Nacht warten", "delay_min": None,
            "score": round(night_score,1), "projected_generation_ml": round(night_forecast_ml),
            "projected_potential_ml": round(current_potential + night_forecast_ml * ventilation_capture),
            "ventilation_capture_fraction": round(ventilation_capture, 3),
            "dryness_g_m3": None, "temperature_c": None, "routine_maturity": round(routine_maturity),
            "confidence": round(_clamp(night_confidence,20,95)), "source": "night_model",
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0] if candidates else None
    current = next((x for x in candidates if x["id"] == "now"), None)
    # Future plans need a meaningful margin over "now"; this prevents multi-hour
    # forecast noise from constantly moving the planned window.
    selected = best
    if best and current and best["id"] != "now" and _f(best["score"]) < _f(current["score"]) + 7.0:
        selected = current

    # A closed room always creates the mandatory "now" candidate above, so
    # selected is guaranteed here. This used to contain an unreachable fallback.
    if selected["id"] == "now":
        summary = "Das aktuelle Lüftungsfenster ist innerhalb der Mehrstundenplanung mindestens gleichwertig."
    elif selected["id"] == "after_night":
        summary = "Die Gesamtplanung bewertet Abwarten bis nach der Nacht derzeit günstiger."
    else:
        summary = f"Das günstigste geplante Lüftungsfenster liegt {selected['label'].lower()}."

    return {
        "active": True, "engine": "v1", "horizon_hours": round(horizon_min/60,1),
        "selected_option_id": selected["id"], "selected_label": selected["label"],
        "selected_delay_min": selected.get("delay_min"), "confidence": selected["confidence"],
        "summary": summary, "pressure": round(pressure), "routine_projection_ml": round(routine_total),
        "routine_maturity": round(routine_maturity), "options": candidates[:8],
    }


def refine_with_plan(recommendation: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    out = dict(recommendation)
    out["day_night_plan"] = plan
    out["planner_engine"] = "v1"
    if not plan.get("active"):
        return out
    kind = str(out.get("kind") or "okay")
    # Real-time control and health/pollen actions remain authoritative.
    if kind in {"close", "continue", "sensor", "pollen_wait"}:
        return out
    selected = str(plan.get("selected_option_id") or "")
    delay = plan.get("selected_delay_min")
    confidence = int(plan.get("confidence",0) or 0)
    if selected.startswith("in_") and delay and confidence >= 55 and kind in {"okay","wait","prepare"}:
        out.update({
            "kind":"wait", "status":"wait", "title":"Geplantes Lüftungsfenster",
            "instruction": f"In etwa {round(int(delay)/60,1):g} h erneut bewerten" if int(delay)>=60 else f"In etwa {delay} min erneut bewerten",
            "summary": str(plan.get("summary") or ""),
            "planner_action": True,
        })
        reasons=list(out.get("reasons") or [])
        reasons.insert(0, f"Mehrstundenplanung: {plan.get('selected_label')} ist aktuell das günstigste Fenster")
        out["reasons"]=reasons[:6]
    elif selected=="after_night" and confidence>=55 and kind in {"okay","wait","prepare"}:
        out.update({"kind":"wait","status":"wait","title":"Bis nach der Nacht beobachten",
                    "instruction":"Nach der Nacht neu bewerten","summary":str(plan.get("summary") or ""),
                    "planner_action":True})
    return out
