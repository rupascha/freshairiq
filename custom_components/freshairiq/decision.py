"""FreshAirIQ Decision & Simulation Engine v6.

Evaluates a small matrix of plausible actions and turns the existing room,
forecast and behavioural models into one explainable best action.  It does not
replace the physical room model; it consumes its outputs.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime

from .routines import project_generation_ml
from .strategy import household_strategy_fit
from math import exp, isfinite


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def _exchange_fraction(rate: float, minutes: float, airflow: float) -> float:
    rate = _clamp(rate, 0.003, 0.30)
    minutes = _clamp(minutes, 1.0, 120.0)
    airflow = _clamp(airflow, 0.35, 2.2)
    return _clamp(1.0 - exp(-(rate * minutes * airflow)), 0.0, 0.92)


def _health_pressure(room: dict[str, Any], options: dict[str, Any]) -> float:
    """0..100 pressure where waiting becomes increasingly undesirable."""
    rh = _f(room.get("humidity"))
    surface = _f(room.get("surface_rh"))
    co2_available = bool(room.get("co2_available", room.get("co2") is not None))
    co2 = _f(room.get("co2")) if co2_available else 0.0
    trend = _f(room.get("humidity_trend_pct_h"))
    high_rh = _f(options.get("high_rh"), 68.0)
    warn_surface = _f(options.get("mould_warn_surface_rh"), 80.0)
    critical_surface = _f(options.get("mould_critical_surface_rh"), 90.0)
    co2_warn = _f(options.get("co2_warn"), 1000.0)
    co2_critical = _f(options.get("co2_critical"), 1400.0)

    pressure = 0.0
    if rh >= high_rh:
        pressure += 35.0 + min((rh - high_rh) * 3.0, 20.0)
    if surface >= warn_surface:
        pressure += 35.0 + min(max(surface - warn_surface, 0.0) * 2.0, 25.0)
    if surface >= critical_surface:
        pressure = max(pressure, 92.0)
    if co2_available and co2 >= co2_warn:
        pressure += 30.0 + min(max(co2 - co2_warn, 0.0) / max(co2_critical - co2_warn, 1.0) * 35.0, 35.0)
    if trend > 0 and rh >= _f(options.get("start_rh"), 62.0):
        pressure += min(trend * 2.5, 18.0)
    return _clamp(pressure, 0.0, 100.0)


def _strategy_adjustment(selected: list[dict[str, Any]], option_id: str, duration: float | None, pressure: float) -> dict[str, float]:
    """Small adherence bonus for similarly good choices; never dominates health."""
    fit = household_strategy_fit(selected, option_id, duration)
    maturity = _f(fit.get("maturity"))
    if maturity < 12.0 or pressure >= 85.0:
        bonus = 0.0
    else:
        maturity_weight = min(maturity / 55.0, 1.0)
        health_guard = _clamp(1.0 - pressure / 85.0, 0.0, 1.0)
        bonus = (_f(fit.get("fit"), 0.5) - 0.5) * 20.0 * maturity_weight * health_guard
    return {
        "strategy_fit": round(_f(fit.get("fit"), 0.5), 3),
        "strategy_follow_probability": round(_f(fit.get("follow"), 0.5) * 100.0, 1),
        "strategy_success_probability": round(_f(fit.get("success"), 0.5) * 100.0, 1),
        "strategy_maturity": round(maturity, 1),
        "strategy_bonus": round(bonus, 2),
    }


def _behaviour_duration(base: float, selected: list[dict[str, Any]], options: dict[str, Any]) -> tuple[float, str | None]:
    """Personalise duration conservatively from actual completed sessions."""
    base = _clamp(base, _f(options.get("min_duration_min"), 3.0), _f(options.get("max_duration_min"), 30.0))
    adjustments: list[tuple[float, float]] = []
    for room in selected:
        samples = int(room.get("behaviour_duration_samples", 0) or 0)
        deviation = room.get("behaviour_avg_duration_deviation_min")
        preferred = room.get("behaviour_preferred_duration_min")
        if samples >= 3 and deviation is not None:
            weight = min(samples / 15.0, 1.0)
            adjustments.append((_clamp(_f(deviation), -6.0, 8.0), weight))
        elif samples >= 5 and preferred is not None:
            adjustments.append((_clamp(_f(preferred) - base, -6.0, 8.0), min(samples / 20.0, 0.65)))
    if not adjustments:
        return round(base, 1), None
    weighted = sum(adj * weight for adj, weight in adjustments) / max(sum(weight for _, weight in adjustments), 0.01)
    # Behaviour may personalise a recommendation, but never fully overrule physics.
    applied = _clamp(weighted * 0.45, -3.0, 4.0)
    duration = _clamp(base + applied, _f(options.get("min_duration_min"), 3.0), _f(options.get("max_duration_min"), 30.0))
    if abs(applied) < 0.4:
        return round(duration, 1), "Bewohnerverhalten bestätigt die physikalische Lüftungsdauer"
    direction = "länger" if applied > 0 else "kürzer"
    return round(duration, 1), f"Lernmodell passt die Dauer um {abs(applied):.1f} min {direction} an"


def _simulate_ventilation(selected: list[dict[str, Any]], duration: float, *, source_ah: float | None = None, source_temp_c: float | None = None) -> dict[str, float]:
    removed = 0.0
    temp_weighted = 0.0
    volume_sum = 0.0
    cost = 0.0
    confidence_values: list[float] = []
    for room in selected:
        potential = _f(room.get("potential_ml"))
        if source_ah is not None:
            potential = (_f(room.get("absolute_humidity")) - float(source_ah)) * max(_f(room.get("volume_m3"), 0.0), 0.0)
        rate = _f(room.get("learned_exchange_rate_per_min"), 0.03)
        airflow = _f(room.get("airflow_factor"), 1.0)
        volume = max(_f(room.get("volume_m3"), 1.0), 1.0)
        fraction = _exchange_fraction(rate, duration, airflow)
        outcome_samples = int(room.get("outcome_feedback_samples", 0) or 0)
        outcome_weight = min(outcome_samples / 8.0, 1.0)
        removed_factor = 1.0 + (_clamp(_f(room.get("outcome_removed_factor"), 1.0), 0.55, 1.55) - 1.0) * outcome_weight
        removed += potential * fraction * removed_factor

        fh = max(_f(room.get("forecast_horizon_min"), duration), 1.0)
        if source_temp_c is not None:
            temp = (float(source_temp_c) - _f(room.get("temperature"))) * fraction
        else:
            temp = _f(room.get("forecast_temperature_change_c"))
        # Temperature does not scale linearly forever; damp longer extrapolation.
        temp_scale = min(duration / fh, 1.0) if duration <= fh else 1.0 + min((duration - fh) / max(fh, 1.0), 1.0) * 0.35
        temp_factor = 1.0 + (_clamp(_f(room.get("outcome_temperature_factor"), 1.0), 0.60, 1.50) - 1.0) * outcome_weight
        temp_weighted += temp * temp_scale * temp_factor * volume
        volume_sum += volume
        base_cost = max(_f(room.get("forecast_cost")), 0.0) * min(duration / fh, 1.8)
        if source_temp_c is not None:
            current_forecast_dt = abs(_f(room.get("forecast_temperature_change_c")))
            future_dt = abs(temp * temp_scale * temp_factor)
            if current_forecast_dt >= 0.05:
                base_cost *= _clamp(future_dt / current_forecast_dt, 0.0, 2.5)
            elif future_dt <= 0.05:
                base_cost = 0.0
        cost += base_cost
        confidence_values.append(_f(room.get("forecast_confidence"), 0.0))
    return {
        "removed_ml": round(removed),
        "temperature_change_c": round(temp_weighted / max(volume_sum, 1.0), 2),
        "cost": round(cost, 4),
        "confidence": round(min(confidence_values) if confidence_values else 0.0),
    }



def _duration_utility(sim: dict[str, float], duration: float, options: dict[str, Any], pressure: float) -> float:
    """Utility for duration optimisation. Health stays dominant; energy penalises over-ventilation."""
    threshold = max(_f(options.get("min_potential_room_ml"), 100.0), 80.0)
    moisture = max(_f(sim.get("removed_ml")), 0.0)
    benefit = min(moisture / threshold * 24.0, 78.0)
    thermal = abs(min(_f(sim.get("temperature_change_c")), 0.0)) * 15.0
    energy = max(_f(sim.get("cost")), 0.0) * 125.0
    # A small time cost creates a natural knee: extra minutes must still deliver useful moisture removal.
    time_cost = max(duration - _f(options.get("min_duration_min"), 3.0), 0.0) * 0.75
    health_support = min(pressure / 100.0 * min(duration, 12.0) * 0.55, 7.0)
    return benefit + health_support - min(thermal + energy, 34.0) - time_cost


def _optimise_duration(
    selected: list[dict[str, Any]],
    seed_duration: float,
    options: dict[str, Any],
    pressure: float,
    *,
    source_ah: float | None = None,
    source_temp_c: float | None = None,
) -> tuple[float, dict[str, float], dict[str, Any]]:
    """Find the shortest near-optimal learned duration instead of blindly extending ventilation.

    The physical model, learned exchange rate and outcome calibration are all already
    consumed by _simulate_ventilation().  We compare minute-by-minute candidates and
    deliberately prefer the shorter duration when two candidates are nearly equal.
    """
    minimum = max(_f(options.get("min_duration_min"), 3.0), 2.0)
    maximum = min(max(_f(options.get("max_duration_min"), 20.0), minimum), 45.0)
    seed = _clamp(seed_duration, minimum, maximum)

    # Include every full minute plus the personalised seed so learning can shift the optimum.
    candidates = sorted(set(
        [round(minimum + i, 1) for i in range(int(maximum - minimum) + 1)]
        + [round(seed, 1), round(maximum, 1)]
    ))
    rows: list[tuple[float, float, dict[str, float]]] = []
    for minutes in candidates:
        sim = _simulate_ventilation(
            selected, minutes, source_ah=source_ah, source_temp_c=source_temp_c
        )
        rows.append((_duration_utility(sim, minutes, options, pressure), minutes, sim))

    best_utility = max((row[0] for row in rows), default=0.0)
    # Near-equal results: choose the shortest duration within 2 utility points of the maximum.
    eligible = [row for row in rows if row[0] >= best_utility - 2.0]
    chosen = min(eligible, key=lambda row: row[1]) if eligible else max(rows, key=lambda row: row[0])
    utility, duration, sim = chosen

    # Marginal yield of another 5 min at the chosen operating point.
    later = min(duration + 5.0, maximum)
    if later > duration + 0.1:
        sim_later = _simulate_ventilation(
            selected, later, source_ah=source_ah, source_temp_c=source_temp_c
        )
        extra_5 = max(_f(sim_later.get("removed_ml")) - _f(sim.get("removed_ml")), 0.0)
        extra_temp = _f(sim_later.get("temperature_change_c")) - _f(sim.get("temperature_change_c"))
        extra_cost = max(_f(sim_later.get("cost")) - _f(sim.get("cost")), 0.0)
    else:
        extra_5, extra_temp, extra_cost = 0.0, 0.0, 0.0

    # Explain how strongly real outcome learning currently calibrates this room set.
    feedback_samples = sum(int(r.get("outcome_feedback_samples", 0) or 0) for r in selected)
    feedback_factor = (
        sum(_f(r.get("outcome_removed_factor"), 1.0) for r in selected) / len(selected)
        if selected else 1.0
    )
    meta = {
        "duration_seed_min": round(seed, 1),
        "duration_optimised_min": round(duration, 1),
        "duration_utility": round(utility, 2),
        "extra_5_min_ml": round(extra_5),
        "extra_5_min_temperature_c": round(extra_temp, 2),
        "extra_5_min_cost": round(extra_cost, 4),
        "outcome_feedback_samples": feedback_samples,
        "outcome_removed_factor": round(feedback_factor, 3),
    }
    return round(duration, 1), sim, meta


def build_decision_simulation(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    recommendation: dict[str, Any],
    *,
    night_forecast_ml: float = 0.0,
    night_confidence: float = 0.0,
    future_outdoor: dict[int, dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate actionable alternatives and optionally refine the recommendation.

    Delayed options use interpolated hourly weather boundaries when the configured
    Home Assistant weather provider supplies temperature and humidity. Missing
    horizons retain the conservative current-condition projection.
    """
    room_keys = [str(x) for x in (recommendation.get("room_keys") or [])]
    selected = [rooms[k] for k in room_keys if k in rooms and rooms[k].get("data_quality") == "ok"]
    kind = str(recommendation.get("kind") or "okay")
    base_duration = _f(recommendation.get("duration_min"), _f(options.get("min_duration_min"), 5.0))
    duration, behaviour_reason = _behaviour_duration(base_duration, selected, options)

    # Running/closing/sensor states are real-time control states and must never be
    # overridden by a speculative future option.
    locked = kind in {"close", "continue", "sensor"}
    options_out: list[dict[str, Any]] = []

    if selected and kind in {"ventilate", "pollen_wait", "wait", "prepare"}:
        pressure = max((_health_pressure(r, options) for r in selected), default=0.0)
        now_duration, sim_now, now_duration_meta = _optimise_duration(
            selected, duration, options, pressure
        )
        thermal_penalty = abs(min(_f(sim_now["temperature_change_c"]), 0.0)) * 14.0
        cost_penalty = _f(sim_now["cost"]) * 120.0
        benefit_score = max(_f(sim_now["removed_ml"]), 0.0) / max(_f(options.get("min_potential_room_ml"), 100.0), 80.0) * 18.0
        now_score = pressure * 1.35 + min(benefit_score, 55.0) - min(thermal_penalty + cost_penalty, 30.0)
        if kind == "pollen_wait":
            now_score -= 70.0
        now_strategy = _strategy_adjustment(selected, "now", now_duration, pressure)
        now_score += _f(now_strategy.get("strategy_bonus"))
        options_out.append({
            "id": "now", "label": "Jetzt lüften", "delay_min": 0, "duration_min": now_duration,
            "score": round(now_score, 1), **sim_now, **now_strategy, **now_duration_meta,
            "assumption": "aktuelle Außenbedingungen",
        })

        trend = max((_f(r.get("humidity_trend_pct_h")) for r in selected), default=0.0)
        future_outdoor = future_outdoor or {}
        for delay in (15, 30, 60):
            boundary = future_outdoor.get(delay)
            routine_generation = 0.0
            routine_maturity = 0.0
            if now is not None:
                routine_generation, routine_maturity = project_generation_ml(selected, now, delay)
            if boundary:
                future_duration, future_sim, future_duration_meta = _optimise_duration(
                    selected, duration, options, pressure,
                    source_ah=_f(boundary.get("absolute_humidity")),
                    source_temp_c=_f(boundary.get("temperature_c")),
                )
                benefit_future = max(_f(future_sim["removed_ml"]), 0.0) / max(_f(options.get("min_potential_room_ml"), 100.0), 80.0) * 18.0
                thermal_future = abs(min(_f(future_sim["temperature_change_c"]), 0.0)) * 14.0
                cost_future = _f(future_sim["cost"]) * 120.0
                health_wait_penalty = pressure * (delay / 60.0) * 0.75
                trend_penalty = max(trend, 0.0) * (delay / 60.0) * 4.0
                future_score = pressure * 1.35 + min(benefit_future, 55.0) - min(thermal_future + cost_future, 30.0) - health_wait_penalty - trend_penalty
                conf = min(_f(future_sim["confidence"]), _f(boundary.get("confidence"), 75.0))
                assumption = f"Wetterprognose: {boundary.get('temperature_c')} °C · {boundary.get('humidity')} %"
            else:
                future_duration, future_sim, future_duration_meta = now_duration, sim_now, dict(now_duration_meta)
                health_wait_penalty = pressure * (delay / 60.0) * 0.75
                trend_penalty = max(trend, 0.0) * (delay / 60.0) * 4.0
                future_score = now_score - health_wait_penalty - trend_penalty - delay * 0.04
                conf = max(_f(sim_now["confidence"]) - delay * 0.35, 20.0)
                assumption = "aktuelle Außenbedingungen konservativ fortgeschrieben"
            if routine_maturity >= 15.0 and routine_generation > 0:
                maturity_weight = min(routine_maturity / 60.0, 1.0)
                generation_ratio = routine_generation / max(_f(options.get("min_potential_room_ml"), 100.0), 80.0)
                routine_penalty = min(
                    generation_ratio * 10.0 * maturity_weight
                    + max(generation_ratio - 1.0, 0.0) * 5.0 * maturity_weight,
                    30.0,
                )
                future_score -= routine_penalty
            if kind in {"wait", "pollen_wait", "prepare"}:
                future_score += 18.0
            wait_strategy = _strategy_adjustment(selected, f"wait_{delay}", future_duration, pressure)
            future_score += _f(wait_strategy.get("strategy_bonus"))
            options_out.append({
                "id": f"wait_{delay}", "label": f"{delay} min warten", "delay_min": delay,
                "duration_min": future_duration, "score": round(future_score, 1), **wait_strategy, **future_duration_meta,
                "removed_ml": future_sim["removed_ml"], "temperature_change_c": future_sim["temperature_change_c"],
                "cost": future_sim["cost"], "confidence": round(conf),
                "assumption": assumption, "future_weather": bool(boundary),
                "routine_generation_ml": round(routine_generation), "routine_maturity": round(routine_maturity),
            })

        if night_forecast_ml > 0:
            night_score = 12.0 - pressure * 0.9 - min(_f(night_forecast_ml) / 20.0, 35.0)
            night_strategy = _strategy_adjustment(selected, "night", None, pressure)
            night_score += _f(night_strategy.get("strategy_bonus"))
            options_out.append({
                "id": "night", "label": "Nacht abwarten", "delay_min": None, "duration_min": None,
                "score": round(night_score, 1), "removed_ml": 0, "temperature_change_c": 0.0, "cost": 0.0, **night_strategy,
                "confidence": round(_clamp(night_confidence, 20.0, 95.0)),
                "assumption": f"Nachtprognose +{round(night_forecast_ml)} ml",
            })

    # Always preserve the existing recommendation when there is no meaningful
    # matrix to compare. This keeps v0.9.5.0 behaviour stable for edge cases.
    best = max(options_out, key=lambda x: x["score"], default=None)
    refined = dict(recommendation)
    changed = False
    reasons = list(refined.get("reasons") or [])
    if behaviour_reason and behaviour_reason not in reasons:
        reasons.append(behaviour_reason)

    if best and not locked:
        if best["id"] == "now" and kind == "ventilate":
            selected_duration = _f(best.get("duration_min"), duration)
            if abs(_f(refined.get("duration_min"), selected_duration) - selected_duration) >= 0.4:
                changed = True
            refined["duration_min"] = selected_duration
            refined["estimated_removed_ml"] = max(round(_f(best.get("removed_ml"))), 0)
            refined["expected_temperature_change_c"] = _f(best.get("temperature_change_c"))
            refined["estimated_reheat_cost"] = _f(best.get("cost"))
        elif str(best["id"]).startswith("wait_") and kind == "ventilate":
            # A wait option can only overrule an immediate action with a real
            # margin. This hysteresis prevents recommendation flapping.
            now = next((x for x in options_out if x["id"] == "now"), None)
            if now and _f(best["score"]) >= _f(now["score"]) + 8.0:
                delay = int(best["delay_min"])
                changed = True
                forecast_based = bool(best.get("future_weather"))
                summary = (
                    "Die Wetterentwicklung macht das Lüften voraussichtlich effizienter als sofortiges Lüften."
                    if forecast_based else
                    "Die Simulation bewertet kurzes Warten derzeit günstiger als sofortiges Lüften."
                )
                refined.update({
                    "kind": "wait", "status": "wait", "title": "Noch kurz warten",
                    "instruction": f"In etwa {delay} min erneut bewerten",
                    "summary": summary,
                    "duration_min": _f(best.get("duration_min"), duration),
                    "estimated_removed_ml": max(round(_f(best.get("removed_ml"))), 0),
                    "expected_temperature_change_c": _f(best.get("temperature_change_c")),
                    "estimated_reheat_cost": _f(best.get("cost")),
                })
                if best.get("future_weather"):
                    reasons.insert(0, f"In {delay} min werden günstigere Außenbedingungen erwartet; prognostiziert sind etwa {max(round(_f(best.get('removed_ml'))), 0)} ml Feuchteabbau")
                else:
                    reasons.insert(0, f"Die beste simulierte Option ist aktuell {delay} min warten")
                if _f(best.get("routine_generation_ml")) >= 25 and _f(best.get("routine_maturity")) >= 20:
                    reasons.append(f"Das gelernte Tagesmuster erwartet während der Wartezeit etwa +{round(_f(best.get('routine_generation_ml')))} ml neue Feuchte")

    if best and best.get("duration_optimised_min") is not None:
        seed = _f(best.get("duration_seed_min"))
        optimum = _f(best.get("duration_optimised_min"))
        extra5 = max(round(_f(best.get("extra_5_min_ml"))), 0)
        if abs(optimum - seed) >= 0.5:
            reasons.append(
                f"Selbstoptimierte Dauer: {optimum:g} min; interner 5-Minuten-Schließcheck erwartet danach nur noch etwa {extra5} ml zusätzlichen Feuchteabbau"
            )
        elif int(best.get("outcome_feedback_samples", 0) or 0) >= 3:
            reasons.append(
                f"Die gelernte Raumreaktion bestätigt etwa {optimum:g} min als effiziente Dauer"
            )

    if best and _f(best.get("strategy_maturity")) >= 20.0 and abs(_f(best.get("strategy_bonus"))) >= 0.8:
        if _f(best.get("strategy_bonus")) > 0:
            reasons.append(
                f"Nutzerstrategie: ähnliche Empfehlungen wurden bisher zu etwa {round(_f(best.get('strategy_follow_probability')))} % umgesetzt"
            )
        else:
            reasons.append("Nutzerstrategie wurde berücksichtigt, die physikalische Bewertung bleibt jedoch maßgeblich")
    refined["reasons"] = reasons[:6]
    refined["decision_engine"] = "v6"
    refined["decision_refined"] = changed
    refined["simulated_options"] = sorted(options_out, key=lambda x: x["score"], reverse=True)
    refined["selected_option_id"] = best.get("id") if best else None
    refined["selected_option_label"] = best.get("label") if best else None
    refined["future_weather_used"] = any(bool(x.get("future_weather")) for x in options_out)
    refined["simulation_note"] = (
        "Stündliche Wetterdaten werden für 15/30/60 Minuten interpoliert. Gelernte Tagesroutinen und die adaptive Nutzerstrategie "
        "dürfen ähnlich gute Optionen verfeinern; Gesundheit und Physik bleiben vorrangig."
    )
    return refined
