"""FreshAirIQ Recommendation Engine v2.

Turns room diagnostics into one prioritised, actionable house recommendation.
The engine is deliberately pure so it can be unit-tested without Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable

from .outdoor_air import pm25_reason, veto_cause


_PROBLEM_LEVELS = {"Elevated", "High", "Very high"}


@dataclass(slots=True)
class Candidate:
    key: str
    name: str
    score: float
    potential_ml: float
    delta: float
    airflow: float
    problem: bool
    urgent: bool
    action: str
    reasons: list[str]


def _f(value: Any, default: float = 0.0) -> float:
    """Return a finite float so corrupted sensor/storage values cannot poison decisions."""
    try:
        out = float(value)
        return out if isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _problem(room: dict[str, Any], options: dict[str, Any]) -> tuple[bool, bool, list[str], float]:
    """Return (problem, urgent, reasons, severity_score)."""
    rh = _f(room.get("humidity"))
    surf = _f(room.get("surface_rh"))
    co2_available = bool(room.get("co2_available", room.get("co2") is not None))
    co2 = _f(room.get("co2")) if co2_available else 0.0
    trend = _f(room.get("humidity_trend_pct_h"))
    high_for = _f(room.get("humidity_high_duration_min"))
    high_rh = _f(options.get("high_rh"), 68.0)
    start_rh = _f(options.get("start_rh"), 62.0)
    mould_warn = _f(options.get("mould_warn_surface_rh"), 80.0)
    mould_critical = _f(options.get("mould_critical_surface_rh"), 90.0)
    co2_warn = _f(options.get("co2_warn"), 1000.0)
    co2_critical = _f(options.get("co2_critical"), 1400.0)

    reasons: list[str] = []
    score = 0.0
    urgent = False

    if rh >= high_rh:
        reasons.append(f"Raumluftfeuchte {round(rh)} % ist zu hoch")
        score += 48 + min((rh - high_rh) * 4, 24)
    elif rh >= start_rh and high_for >= 20:
        reasons.append(f"Raumluftfeuchte liegt seit {round(high_for)} min über {round(start_rh)} %")
        score += 18 + min(high_for / 15, 12)

    if surf >= mould_critical:
        reasons.append(f"Oberflächenfeuchte {round(surf)} %: sehr hohes Schimmelrisiko")
        score += 90
        urgent = True
    elif surf >= mould_warn:
        reasons.append(f"Oberflächenfeuchte {round(surf)} %: erhöhtes Schimmelrisiko")
        score += 55
    elif room.get("mould_level") in _PROBLEM_LEVELS and surf >= 70:
        reasons.append(f"Oberflächenfeuchte {round(surf)} % ist auffällig")
        score += 20

    if co2_available and co2 >= co2_critical:
        reasons.append(f"CO₂ {round(co2)} ppm ist stark erhöht")
        score += 80
        urgent = True
    elif co2_available and co2 >= co2_warn:
        reasons.append(f"CO₂ {round(co2)} ppm ist erhöht")
        score += 45

    if trend >= 3.0 and rh >= start_rh:
        reasons.append(f"Luftfeuchte steigt schnell ({trend:+.1f} %-Punkte/h)")
        score += 12
    elif trend <= -3.0 and rh < high_rh:
        # A naturally falling trend makes an early intervention less valuable.
        score -= 8

    return bool(reasons), urgent, reasons, max(score, 0.0)


def _candidate(room: dict[str, Any], options: dict[str, Any], threshold_ml: float) -> Candidate:
    problem, urgent, problem_reasons, severity = _problem(room, options)
    potential = max(_f(room.get("realistic_potential_ml", room.get("potential_ml"))), 0.0)
    delta = _f(room.get("delta_g_m3"))
    airflow = max(0.5, min(_f(room.get("airflow_factor"), 1.0), 1.5))
    cost = max(_f(room.get("next_5_min_cost")), 0.0)
    temp_loss = max(-_f(room.get("temp_next_5_min_c")), 0.0)

    # Benefit grows with useful removable moisture, dry-air gradient and airflow.
    benefit = min(potential / max(threshold_ml, 100.0) * 35.0, 35.0)
    benefit += min(max(delta, 0.0) * 4.0, 20.0)
    benefit += (airflow - 1.0) * 18.0

    # Penalise thermal/monetary cost, but never enough to suppress urgent health risk.
    penalty = min(temp_loss * 8.0, 18.0) + min(cost * 45.0, 18.0)
    score = severity + benefit - (0.25 * penalty if urgent else penalty)
    # Per-room goal order is a soft optimisation weight, never a safety veto.
    # The first currently open and achievable goal gets the strongest boost.
    gs = room.get("goal_state") if isinstance(room.get("goal_state"), dict) else {}
    for idx, goal in enumerate(gs.get("goals", [])):
        if goal.get("active") and not goal.get("reached") and goal.get("achievable_now"):
            score += max(12.0 - idx * 4.0, 4.0)
            break

    reasons = list(problem_reasons)
    if delta > 0:
        reasons.append(f"Außen-/Referenzluft ist {delta:.1f} g/m³ trockener")
    if potential >= 1:
        reasons.append(f"Etwa {round(potential)} ml sind aktuell entfernbar")
    if airflow >= 1.12:
        reasons.append("Windrichtung unterstützt den Luftwechsel")
    elif airflow <= 0.88:
        reasons.append("Windrichtung bremst den Luftwechsel")

    return Candidate(
        key=str(room.get("key", "")), name=str(room.get("name", room.get("key", "Raum"))),
        score=score, potential_ml=potential, delta=delta, airflow=airflow,
        problem=problem, urgent=urgent, action=str(room.get("action", "Okay")), reasons=reasons,
    )


def _parse_pairs(raw: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in str(raw or "").split(","):
        keys = [x.strip() for x in item.split("+") if x.strip()]
        if len(keys) == 2 and keys[0] != keys[1]:
            pairs.append((keys[0], keys[1]))
    return pairs


def _clean_reasons(items: Iterable[str], limit: int = 4) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out



def _floor_label(value: Any) -> str:
    raw = str(value or "").strip()
    return {"ground_floor":"Erdgeschoss","ground floor":"Erdgeschoss","Ground Floor":"Erdgeschoss","upper_floor":"Obergeschoss","upper floor":"Obergeschoss","Upper Floor":"Obergeschoss","basement":"Kellergeschoss","base_floor":"Kellergeschoss","base floor":"Kellergeschoss","Basement":"Kellergeschoss","attic":"Dachgeschoss","Attic":"Dachgeschoss"}.get(raw, raw or "Stockwerk")

def _scope_for(selected: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not selected:
        return "house", None
    floors = {str(r.get("floor") or "") for r in selected}
    if len(selected) == 1:
        return "room", next(iter(floors), None)
    if len(floors) == 1:
        return "floor", next(iter(floors), None)
    return "house", None

def build_recommendation(
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    *,
    threshold_ml: float,
    total_potential_ml: float,
    recommended_duration_min: float,
    pollen_index: float = 0.0,
    pollen_blocked: bool = False,
    night_forecast_ml: float = 0.0,
    outdoor_pm25: float | None = None,
    outdoor_pm25_blocked: bool = False,
) -> dict[str, Any]:
    """Compose the single best action for the home at this moment."""
    # 0.26.4.7: outdoor fine dust (PM2.5) is a second outdoor-air veto next to
    # pollen. Both postpone normal airing; critical CO₂/mould keep priority.
    pollen_only = bool(pollen_blocked)
    pm25_only = bool(outdoor_pm25_blocked)
    pollen_blocked = pollen_only or pm25_only
    veto = veto_cause(pollen_only, pm25_only)

    def _outdoor_burden(context: str) -> list[str]:
        pm = float(outdoor_pm25 or 0.0)
        notes = []
        if pollen_only:
            notes.append({
                "multi": f"Pollenindex {pollen_index:.1f}: Belastung beachten; kritische Luftqualität hat aktuell Vorrang",
                "co2": f"Pollenindex {pollen_index:.1f}: Belastung beachten; die kritische Luftqualität hat aktuell Vorrang",
                "mould": f"Pollenindex {pollen_index:.1f}; Schimmelschutz hat bei wirksamer Entfeuchtung aktuell Vorrang",
            }[context])
        if pm25_only:
            notes.append({
                "multi": f"Feinstaub draußen {pm:.0f} µg/m³: Belastung beachten; kritische Luftqualität hat aktuell Vorrang",
                "co2": f"Feinstaub draußen {pm:.0f} µg/m³: Belastung beachten; die kritische Luftqualität hat aktuell Vorrang",
                "mould": f"Feinstaub draußen {pm:.0f} µg/m³; Schimmelschutz hat bei wirksamer Entfeuchtung aktuell Vorrang",
            }[context])
        return notes
    valid = [r for r in rooms.values() if r.get("calculation_enabled", True) and r.get("data_quality") == "ok"]
    bad = [r for r in rooms.values() if r.get("calculation_enabled", True) and r.get("data_quality") != "ok"]
    active = [r for r in valid if r.get("active")]
    def _goal_state(room: dict[str, Any]) -> dict[str, Any]:
        return room.get("goal_state") if isinstance(room.get("goal_state"), dict) else {}

    def _open_achievable_goals(room: dict[str, Any]) -> list[dict[str, Any]]:
        return [g for g in _goal_state(room).get("goals", [])
                if g.get("active") and not g.get("reached") and g.get("achievable_now")]

    def _has_nonhumidity_opportunity(room: dict[str, Any]) -> bool:
        return any(g.get("id") in {"co2", "temperature"} for g in _open_achievable_goals(room))

    closing = [r for r in active if r.get("action") == "Close" or r.get("close_recommended") or _goal_state(r).get("hard_close")]

    def result(kind: str, status: str, title: str, instruction: str, summary: str, *,
               selected: list[dict[str, Any]] | None = None, reasons: list[str] | None = None,
               severity: str = "neutral", duration: float | None = None,
               removed: float = 0.0, secondary: str = "") -> dict[str, Any]:
        selected = selected or []
        # Action metrics are carried with the recommendation so forecast and
        # recommendation literally expose the same physical state.
        temp = sum(_f(r.get("forecast_temperature_change_c")) for r in selected) / max(len(selected), 1) if selected else 0.0
        cost = sum(max(_f(r.get("forecast_cost")), 0.0) for r in selected)
        conf = min((_f(r.get("forecast_confidence"), 0.0) for r in selected), default=0.0)
        recommendation_scope, recommendation_floor = _scope_for(selected)
        return {
            "engine": "v3",
            "recommendation_scope": recommendation_scope,
            "recommendation_floor": recommendation_floor,
            "recommendation_floor_label": _floor_label(recommendation_floor) if recommendation_floor else None,
            "kind": kind,
            "status": status,
            "title": title,
            "instruction": instruction,
            "summary": summary,
            "reasons": _clean_reasons(reasons or [], 4),
            "room_keys": [str(r.get("key")) for r in selected],
            "room_names": [str(r.get("name", r.get("key", "Raum"))) for r in selected],
            "duration_min": round(float(duration), 1) if duration is not None else None,
            "estimated_removed_ml": round(max(float(removed), 0.0)),
            "severity": severity,
            "secondary": secondary,
            "expected_temperature_change_c": round(temp, 2),
            "estimated_reheat_cost": round(cost, 4),
            "forecast_confidence": int(round(conf)),
        }

    # v0.25.0.2: isolate faulty rooms while valid rooms remain actionable.
    if bad and not valid:
        names = ", ".join(str(r.get("name", r.get("key"))) for r in bad[:3])
        return result("sensor", "sensor_error", "Sensoren prüfen", names,
                      "Eine belastbare Lüftungsentscheidung ist erst mit plausiblen Messwerten möglich.",
                      selected=bad[:3], reasons=["Messwerte fehlen oder sind unplausibel"], severity="danger")

    # Protection-priority contract (v0.26.2.13)
    # --------------------------------------------
    # Critical health/protection limits must be resolved before normal comfort
    # optimisation.  Importantly, "urgent" is not synonymous with "always
    # open a window": critical CO2 needs an air exchange even when humidity or
    # pollen conditions are unfavourable, while critical mould/surface moisture
    # only benefits from outdoor ventilation when the reference air can actually
    # remove moisture.  This keeps the safety reason authoritative without
    # recommending a physically counterproductive action.
    co2_critical = _f(options.get("co2_critical"), 1400.0)
    mould_critical = _f(options.get("mould_critical_surface_rh"), 90.0)
    close_delta = max(_f(options.get("close_delta"), 0.4), 0.0)
    critical_co2_rooms = [
        r for r in valid
        if bool(r.get("co2_available", r.get("co2") is not None))
        and _f(r.get("co2")) >= co2_critical
        and not r.get("stabilizing", False)
    ]
    critical_mould_rooms = [
        r for r in valid
        if _f(r.get("surface_rh")) >= mould_critical
        and not r.get("stabilizing", False)
    ]

    critical_room_keys = {str(r.get("key")) for r in (critical_co2_rooms + critical_mould_rooms)}
    if len(critical_room_keys) > 1:
        mould_actions, mould_blocked = [], []
        for r in critical_mould_rooms:
            delta = _f(r.get("delta_g_m3")); potential = _f(r.get("realistic_potential_ml", r.get("potential_ml")))
            drying = delta > close_delta and potential > 0.0 and not _goal_state(r).get("hard_close")
            (mould_actions if drying else mould_blocked).append(r)
        # A CO2-critical room that already released an authoritative close
        # signal has reached the configured hard session endpoint (under
        # critical CO2, low-return and thermal-close are suppressed upstream).
        # Close/reassess that room instead of contradicting the live coach.
        co2_reassess = [r for r in critical_co2_rooms if r.get("active") and _goal_state(r).get("hard_close")]
        co2_actionable = [r for r in critical_co2_rooms if r not in co2_reassess]
        actionable = list(co2_actionable)
        keys = {str(r.get("key")) for r in actionable}
        actionable += [r for r in mould_actions if str(r.get("key")) not in keys]
        if actionable:
            conflict = pollen_blocked or any(_f(r.get("delta_g_m3")) <= 0.0 or _f(r.get("forecast_temperature_change_c")) <= -1.0 for r in critical_co2_rooms)
            duration = min(float(recommended_duration_min), 5.0) if critical_co2_rooms and conflict else float(recommended_duration_min)
            active_now = [r for r in actionable if r.get("active")]; to_open = [r for r in actionable if not r.get("active")]
            reasons = [f"{r.get('name', r.get('key', 'Raum'))}: CO₂ {round(_f(r.get('co2')))} ppm ist stark erhöht" for r in critical_co2_rooms]
            reasons += [f"{r.get('name', r.get('key', 'Raum'))}: maximale Schutzlüftungsphase erreicht – schließen und CO₂ unmittelbar neu bewerten" for r in co2_reassess]
            reasons += [f"{r.get('name', r.get('key', 'Raum'))}: Oberflächenfeuchte {round(_f(r.get('surface_rh')))} %; trocknere Referenzluft kann jetzt entfeuchten" for r in mould_actions]
            reasons += [f"{r.get('name', r.get('key', 'Raum'))}: kritische Oberflächenfeuchte; Lüften würde aktuell nicht zuverlässig entfeuchten – geschlossen lassen" for r in mould_blocked]
            if pollen_blocked and critical_co2_rooms: reasons.extend(_outdoor_burden("multi"))
            parts=[]
            if to_open: parts.append(", ".join(str(r.get("name",r.get("key","Raum"))) for r in to_open)+f" öffnen · ca. {max(round(duration),1)} min")
            if active_now: parts.append(", ".join(str(r.get("name",r.get("key","Raum"))) for r in active_now)+" offen lassen")
            if co2_reassess: parts.append(", ".join(str(r.get("name",r.get("key","Raum"))) for r in co2_reassess)+" schließen · CO₂ neu bewerten")
            if mould_blocked: parts.append(", ".join(str(r.get("name",r.get("key","Raum"))) for r in mould_blocked)+" geschlossen lassen")
            return result("ventilate" if to_open else "continue", "critical_multiroom", "Schutzlüftung empfohlen" if critical_co2_rooms else "Feuchte kritisch", " · ".join(parts), "FreshAirIQ bündelt gleichzeitig kritische Räume, wenn dieselbe Schutzmaßnahme hilft, und trennt gegensätzliche Maßnahmen raumweise.", selected=actionable, reasons=reasons, severity="danger", duration=duration, removed=sum(max(_f(r.get("realistic_potential_ml",r.get("potential_ml"))),0.0) for r in actionable), secondary="Nach dem Schutzluftwechsel werden alle kritischen Räume und Zielkonflikte neu bewertet.")
        if co2_reassess:
            names=", ".join(str(r.get("name",r.get("key","Raum"))) for r in co2_reassess)
            reasons=[f"{r.get('name',r.get('key','Raum'))}: CO₂ {round(_f(r.get('co2')))} ppm bleibt kritisch; maximale Schutzlüftungsphase ist erreicht" for r in co2_reassess]
            reasons += [f"{r.get('name',r.get('key','Raum'))}: kritische Oberflächenfeuchte; Außen-/Referenzluft bietet keinen ausreichenden Trocknungsvorteil" for r in mould_blocked]
            return result("close", "critical_co2_reassess", "Schutzlüftung neu bewerten", names+" schließen · CO₂ unmittelbar neu bewerten", "Die maximale Schutzlüftungsphase ist erreicht. FreshAirIQ beendet den aktuellen Luftwechsel kontrolliert und bewertet die weiterhin kritische Luftqualität anschließend neu.", selected=co2_reassess, reasons=reasons, severity="danger", secondary="Bleibt CO₂ kritisch, wird nach der Neubewertung erneut ein kurzer Luftaustausch empfohlen.")
        active_blocked=[r for r in mould_blocked if r.get("active")]
        reasons=[f"{r.get('name',r.get('key','Raum'))}: Oberflächenfeuchte {round(_f(r.get('surface_rh')))} % kritisch; Außen-/Referenzluft bietet keinen ausreichenden Trocknungsvorteil" for r in mould_blocked]
        return result("close" if active_blocked else "wait", "critical_mould_wait", "Feuchte kritisch – Lüften derzeit ungünstig", (", ".join(str(r.get("name",r.get("key","Raum"))) for r in active_blocked)+" schließen" if active_blocked else "Außenbedingungen abwarten · Feuchtequelle wenn möglich begrenzen"), "Mehrere Räume haben kritische Oberflächenfeuchte, aber Lüften würde sie aktuell nicht zuverlässig entfeuchten.", selected=mould_blocked, reasons=reasons, severity="danger", secondary="Sobald die Referenzluft wirksam entfeuchten kann, werden alle geeigneten kritischen Räume gemeinsam priorisiert.")

    if critical_co2_rooms:
        r = max(critical_co2_rooms, key=lambda x: _f(x.get("co2")))
        name = str(r.get("name", r.get("key", "Raum")))
        co2 = _f(r.get("co2"))
        delta = _f(r.get("delta_g_m3"))
        temp_change = _f(r.get("forecast_temperature_change_c"))
        conflict = delta <= 0.0 or temp_change <= -1.0 or pollen_blocked
        duration = min(float(recommended_duration_min), 5.0) if conflict else float(recommended_duration_min)
        reasons = [f"{name}: CO₂ {round(co2)} ppm ist stark erhöht"]
        if delta < 0.0:
            reasons.append(f"Außen-/Referenzluft ist {abs(delta):.1f} g/m³ feuchter; der notwendige kurze Luftaustausch hat aktuell Vorrang")
        if temp_change <= -1.0:
            reasons.append(f"Temperaturprognose {temp_change:+.1f} °C; deshalb nur kurz und effizient lüften")
        if pollen_blocked:
            reasons.extend(_outdoor_burden("co2"))
        is_active = bool(r.get("active"))
        if is_active and _goal_state(r).get("hard_close"):
            reasons.append("Die maximale Schutzlüftungsphase ist erreicht; schließen und CO₂ unmittelbar neu bewerten")
            return result(
                "close", "critical_co2_reassess", "Schutzlüftung neu bewerten", f"{name} schließen · CO₂ neu bewerten",
                "Der notwendige Luftaustausch wurde bis zum konfigurierten Schutzendpunkt durchgeführt. FreshAirIQ beendet die aktuelle Phase kontrolliert und bewertet die weiterhin kritische Luftqualität anschließend neu.",
                selected=[r], reasons=reasons, severity="danger",
                secondary="Bleibt CO₂ kritisch, wird nach der Neubewertung erneut ein kurzer Luftaustausch empfohlen.",
            )
        return result(
            "continue" if is_active else "ventilate", "critical_co2", "Luftqualität kritisch",
            (f"{name} kurz offen lassen · ca. {max(round(duration), 1)} min" if conflict else f"{name} offen lassen · ca. {max(round(duration), 1)} min") if is_active else (f"{name} kurz lüften · ca. {max(round(duration), 1)} min" if conflict else f"{name} lüften · ca. {max(round(duration), 1)} min"),
            "Der CO₂-Wert hat die kritische Schutzgrenze erreicht. FreshAirIQ priorisiert den notwendigen Luftaustausch und begrenzt Zielkonflikte soweit möglich.",
            selected=[r], reasons=reasons, severity="danger", duration=duration,
            removed=max(_f(r.get("realistic_potential_ml", r.get("potential_ml"))), 0.0),
            secondary="Nach dem kurzen Luftaustausch werden CO₂, Feuchte und Temperatur neu bewertet.",
        )

    if critical_mould_rooms:
        # For surface-moisture protection, choose the worst room. Outdoor
        # ventilation is only a valid remedy when it has a real drying effect.
        r = max(critical_mould_rooms, key=lambda x: _f(x.get("surface_rh")))
        name = str(r.get("name", r.get("key", "Raum")))
        surf = _f(r.get("surface_rh"))
        delta = _f(r.get("delta_g_m3"))
        potential = _f(r.get("realistic_potential_ml", r.get("potential_ml")))
        drying_possible = delta > close_delta and potential > 0.0 and not _goal_state(r).get("hard_close")
        if drying_possible:
            reasons = [f"{name}: Oberflächenfeuchte {round(surf)} %: sehr hohes Schimmelrisiko",
                       f"Außen-/Referenzluft ist {delta:.1f} g/m³ trockener"]
            if pollen_blocked:
                reasons.extend(_outdoor_burden("mould"))
            is_active = bool(r.get("active"))
            return result(
                "continue" if is_active else "ventilate", "critical_mould", "Feuchte kritisch", (f"{name} offen lassen · ca. {max(round(recommended_duration_min), 1)} min" if is_active else f"{name} jetzt lüften · ca. {max(round(recommended_duration_min), 1)} min"),
                "Die kritische Oberflächenfeuchte kann mit der aktuell trockeneren Außen-/Referenzluft wirksam reduziert werden.",
                selected=[r], reasons=reasons, severity="danger", duration=recommended_duration_min, removed=max(potential, 0.0),
                secondary="FreshAirIQ bewertet die Oberflächenfeuchte und den Lüftungsnutzen währenddessen weiter.",
            )
        why = [f"{name}: Oberflächenfeuchte {round(surf)} %: sehr hohes Schimmelrisiko"]
        if delta <= close_delta:
            why.append(f"Außen-/Referenzluft bietet aktuell keinen ausreichenden Trocknungsvorteil ({delta:+.1f} g/m³)")
        elif potential <= 0.0:
            why.append("Die aktuelle Prognose zeigt keinen positiven Feuchteabbau durch Lüften")
        if _goal_state(r).get("hard_close"):
            why.append("Eine aktive Schutzgrenze verhindert derzeit weiteres Lüften")
        is_active = bool(r.get("active"))
        return result(
            "close" if is_active else "wait", "critical_mould_wait", "Feuchte kritisch – Lüften derzeit ungünstig",
            (f"{name} schließen · Feuchtequelle wenn möglich begrenzen" if is_active else "Außenbedingungen abwarten · Feuchtequelle wenn möglich begrenzen"),
            "Die Oberflächenfeuchte ist kritisch, aber Lüften würde das Feuchteproblem aktuell nicht zuverlässig verbessern. FreshAirIQ hält die Schutzwarnung aktiv, statt eine kontraproduktive Lüftung zu empfehlen.",
            selected=[r], reasons=why, severity="danger",
            secondary="Sobald die Außen-/Referenzluft wirksam entfeuchten kann, wird Lüften zur höchsten Priorität.",
        )

    # Moisture-source events outrank a normal close/continue message. During a
    # shower, bath or sauna event the measured room balance may rise even while
    # ventilation is physically removing water. FreshAirIQ therefore explains
    # the source and keeps useful ventilation active instead of calling that
    # rise a failed ventilation session.
    source_active = [r for r in valid if r.get("moisture_source_active")]
    source_running = [r for r in source_active if r.get("active") and r.get("action") == "Continue ventilating" and not r.get("close_recommended") and _f(r.get("delta_g_m3")) > _f(options.get("close_delta"), 0.4)]
    if source_running:
        names = " + ".join(str(r.get("name", r.get("key"))) for r in source_running)
        labels = "/".join(dict.fromkeys(str(r.get("moisture_source_label") or "Feuchtequelle") for r in source_running))
        confidence = min((int(_f(r.get("moisture_source_confidence"))) for r in source_running), default=0)
        generated_rate_h = sum(max(_f(r.get("moisture_source_rate_ml_min")), 0.0) for r in source_running) * 60.0
        physical = sum(max(_f(r.get("forecast_physical_moisture_effect_ml", r.get("forecast_moisture_effect_ml"))), 0.0) for r in source_running)
        horizon = max(int(round(_f(source_running[0].get("forecast_horizon_min"), options.get("forecast_horizon_min", 5)))), 1)
        reasons = [
            f"{labels} wahrscheinlich aktiv · {confidence} % Sicherheit",
            f"Geschätzte interne Feuchteproduktion aktuell rund +{round(generated_rate_h)} ml/h",
            f"Außen-/Referenzluft bleibt trockener; Lüften kann in {horizon} min physikalisch etwa {round(physical)} ml abführen",
        ]
        return result(
            "continue", "moisture_source_active", f"{labels} erkannt", f"{names} offen lassen",
            str(source_running[0].get("moisture_source_message") or "Die Luftfeuchte steigt durch eine aktive interne Feuchtequelle. FreshAirIQ trennt Feuchteproduktion und Lüftungsabfuhr."),
            selected=source_running, reasons=reasons, severity="warning", duration=None, removed=physical,
            secondary="Nach Ende der Feuchtequelle berechnet FreshAirIQ die notwendige Nachlüftung neu.",
        )

    source_closed = [r for r in source_active if not r.get("active") and _f(r.get("delta_g_m3")) > max(_f(options.get("close_delta"), 0.4), 0.4)]
    if source_closed:
        chosen_source = max(source_closed, key=lambda r: _f(r.get("moisture_source_rate_ml_min")))
        name = str(chosen_source.get("name", chosen_source.get("key", "Raum")))
        label = str(chosen_source.get("moisture_source_label") or "Feuchtequelle")
        conf = int(_f(chosen_source.get("moisture_source_confidence")))
        return result(
            "ventilate", "moisture_source_active", f"{label} erkannt", f"{name} jetzt lüften",
            str(chosen_source.get("moisture_source_message") or "Im Raum wird aktuell zusätzliche Feuchtigkeit erzeugt und die Referenzluft ist trockener. Frühzeitiges Lüften begrenzt den Feuchteanstieg."),
            selected=[chosen_source], reasons=[f"{label} wahrscheinlich aktiv · {conf} % Sicherheit", f"Außen-/Referenzluft ist {_f(chosen_source.get('delta_g_m3')):.1f} g/m³ trockener"],
            severity="warning", duration=recommended_duration_min, removed=max(_f(chosen_source.get("forecast_moisture_effect_ml")), 0.0),
        )

    if closing:
        names = " + ".join(str(r.get("name", r.get("key"))) for r in closing)
        horizon = max(int(round(_f(closing[0].get("forecast_horizon_min"), options.get("forecast_horizon_min", 5)))), 1)
        remaining_effect = sum(max(_f(r.get("forecast_moisture_effect_ml", r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml")))), 0.0) for r in closing)
        return result("close", "close_windows", "Jetzt schließen", f"{names} schließen",
                      "Das Lüftungsziel ist erreicht; weiteres Lüften bringt nur noch wenig Zusatznutzen.",
                      selected=closing, reasons=[f"Im eingestellten Prognosefenster von {horizon} Minuten wären noch etwa {round(remaining_effect)} ml Feuchteabbau möglich; der kurzfristige Zusatznutzen liegt bereits unter der Schließschwelle"],
                      severity="warning")

    if active:
        # Running sessions are a single house action. Continue unless at least one room asks to close.
        names = " + ".join(str(r.get("name", r.get("key"))) for r in active)
        horizon = max(int(round(_f(active[0].get("forecast_horizon_min"), options.get("forecast_horizon_min", 5)))), 1)
        effect = sum(_f(r.get("forecast_moisture_effect_ml", r.get("forecast_5_min_moisture_effect_ml", r.get("moisture_effect_next_5_min_ml")))) for r in active)
        elapsed = max((_f(r.get("session_elapsed_min")) for r in active), default=0.0)
        remaining = max(float(recommended_duration_min) - elapsed, 0.0)
        reasons = [f"Weitere {horizon} Minuten entfernen voraussichtlich etwa {round(max(effect, 0.0))} ml"]
        if any(_f(r.get("airflow_factor"), 1) >= 1.12 for r in active):
            reasons.append("Windrichtung unterstützt den aktuellen Luftwechsel")
        restricted = [r for r in active if r.get("cover_learning_blocked")]
        if restricted:
            max_closed = max((max((_f(x.get("closed_percent")) for x in ((r.get("cover_learning_guard") or {}).get("affected") or []) if isinstance(x, dict)), default=0.0) for r in restricted), default=0.0)
            reasons.append(f"Rollo/Jalousie teilweise geschlossen ({max_closed:.0f} %): für bessere Lüftungswirkung weiter öffnen; diese Session wird nicht als normale Lernprobe verwendet")
        return result("continue", "ventilation_running", "Weiterlüften", f"{names} offen lassen · noch ca. {max(round(remaining),1)} min",
                      "FreshAirIQ bewertet Nutzen und Temperaturverlust während der laufenden Lüftung weiter.",
                      selected=active, reasons=reasons, severity="good", duration=remaining, removed=max(effect, 0.0))

    candidates = [_candidate(r, options, threshold_ml) for r in valid
                  if (r.get("action") in {"Ventilate", "Ventilate for cooling"} or _has_nonhumidity_opportunity(r))
                  and not _goal_state(r).get("hard_close")
                  and not r.get("stabilizing", False)
                  and not r.get("recently_ventilated", False)]
    candidate_by_key = {c.key: c for c in candidates}
    room_by_key = {str(r.get("key")): r for r in valid}
    problem_rooms = []
    blocked_problem_rooms = []
    for r in valid:
        problem, urgent, reasons, severity = _problem(r, options)
        if problem:
            row = (r, urgent, reasons, severity)
            problem_rooms.append(row)
            # 0.26.4.7: a room shown as "Wait" only because of the repeat
            # cooldown is not blocked by physics; do not explain it as such.
            if r.get("action") in {"Do not ventilate", "Wait"} and not r.get("repeat_cooldown_demoted"):
                blocked_problem_rooms.append(row)

    # Hotfix v0.17.0.1:
    # A non-critical problem room must not bypass the physical usefulness
    # thresholds. Previously any high-RH/problem candidate won via max(targeted),
    # even with only a few ml removable while the house-wide balance was negative.
    #
    # Urgent health cases (critical surface RH / critical CO2) remain authoritative.
    default_room_potential = max(_f(options.get("min_potential_room_ml"), 100.0), 0.0)
    def room_threshold(room: dict[str, Any]) -> float:
        # Coordinator resolves optional per-room automatic/percentage/fixed thresholds.
        # Falling back keeps compatibility with older/isolated recommendation tests.
        return max(_f(room.get("ventilation_threshold_effective_ml"), default_room_potential), 0.0)
    house_physics_favourable = total_potential_ml > 0.0
    targeted = [
        c for c in candidates
        if c.problem and (
            c.urgent
            or _has_nonhumidity_opportunity(room_by_key.get(c.key, {}))
            or (house_physics_favourable and c.potential_ml >= room_threshold(room_by_key.get(c.key, {})))
        )
    ]
    house_ready = total_potential_ml >= threshold_ml

    # A configured cross-ventilation pair is preferred when both rooms can use
    # the outside air and it improves the utility of the selected action.
    chosen: list[Candidate] = []
    best_pair: tuple[float, Candidate, Candidate] | None = None
    for a, b in _parse_pairs(options.get("cross_ventilation_pairs")):
        ca, cb = candidate_by_key.get(a), candidate_by_key.get(b)
        same_zone = False
        if ca and cb:
            ra, rb = room_by_key.get(a, {}), room_by_key.get(b, {})
            same_zone = str(ra.get("floor", "")) == str(rb.get("floor", ""))
            explicit_links = str(options.get("cross_zone_connections", ""))
            same_zone = same_zone or f"{a}+{b}" in explicit_links or f"{b}+{a}" in explicit_links
        pair_has_safe_override = bool(
            (ca and ca.urgent) or (cb and cb.urgent)
        )
        pair_has_meaningful_problem = bool(
            house_physics_favourable
            and (
                (ca and ca.problem and ca.potential_ml >= room_threshold(room_by_key.get(ca.key, {})))
                or (cb and cb.problem and cb.potential_ml >= room_threshold(room_by_key.get(cb.key, {})))
            )
        )
        if ca and cb and same_zone and (house_ready or pair_has_safe_override or pair_has_meaningful_problem):
            pair_score = ca.score + cb.score + 18.0  # cross-flow bonus
            if best_pair is None or pair_score > best_pair[0]:
                best_pair = (pair_score, ca, cb)
    if best_pair:
        chosen = [best_pair[1], best_pair[2]]
    elif house_ready and candidates:
        # Normal ventilation is a HOUSE decision first.  Do not let a merely
        # elevated single room pre-empt a useful whole-house opportunity.
        # Select the meaningful contributors to the house threshold; room
        # scores only order them.
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        meaningful = [c for c in ranked if c.potential_ml >= max(20.0, min(room_threshold(room_by_key.get(c.key, {})), threshold_ml * 0.10))]
        pool = meaningful or ranked
        chosen = []
        accumulated = 0.0
        for c in pool:
            chosen.append(c)
            accumulated += c.potential_ml
            if accumulated >= threshold_ml and len(chosen) >= 2:
                break
    elif targeted:
        # Below the house threshold a meaningful non-critical room problem may
        # still justify a targeted recommendation.
        chosen = [max(targeted, key=lambda c: c.score)]
    elif candidates and any(_has_nonhumidity_opportunity(room_by_key.get(c.key, {})) for c in candidates):
        # CO2 and thermal comfort are first-class ventilation goals. They may
        # justify ventilation even when moisture removal is neutral/negative.
        # Safety/hard-close filtering happened when candidates were built.
        goal_candidates = [c for c in candidates if _has_nonhumidity_opportunity(room_by_key.get(c.key, {}))]
        chosen = [max(goal_candidates, key=lambda c: c.score)]

    if chosen and pollen_blocked and not any(c.urgent for c in chosen):
        names = ", ".join(c.name for c in chosen)
        summary = {
            "pm25": f"{names} würden von Lüftung profitieren, die aktuelle Feinstaubbelastung draußen spricht aber gegen ein Öffnen.",
            "pollen_and_pm25": f"{names} würden von Lüftung profitieren, die aktuelle Pollen- und Feinstaubbelastung spricht aber gegen ein Öffnen.",
        }.get(str(veto), f"{names} würden von Lüftung profitieren, die aktuelle Pollenbelastung spricht aber gegen ein Öffnen.")
        reasons = []
        if pollen_only:
            reasons.append(f"Pollenindex {pollen_index:.1f} liegt über dem eingestellten Grenzwert")
        if pm25_only:
            reasons.append(pm25_reason(outdoor_pm25, options))
        rec = result("pollen_wait", "pollen_warning", "Lüften verschieben", "Fenster vorerst geschlossen lassen",
                     summary,
                     selected=[room_by_key[c.key] for c in chosen],
                     reasons=reasons, severity="warning")
        rec["outdoor_veto_cause"] = veto
        return rec

    if chosen:
        selected_rooms = [room_by_key[c.key] for c in chosen]
        names = " + ".join(c.name for c in chosen)
        removed = sum(c.potential_ml for c in chosen)
        has_problem = any(c.problem for c in chosen)
        is_pair = len(chosen) == 2 and best_pair is not None
        chosen_scope, chosen_floor = _scope_for(selected_rooms)
        title = "Jetzt querlüften" if is_pair else (f"{_floor_label(chosen_floor)} lüften" if chosen_scope == "floor" else ("Jetzt gezielt lüften" if has_problem and not house_ready else "Jetzt lüften"))
        opening_labels=[]
        for rr in selected_rooms:
            contacts=list(rr.get("contact_entities") or [])
            if contacts:
                opening_labels.append(f"{rr.get('name')}: " + ", ".join(str(x).split('.')[-1].replace('_',' ') for x in contacts))
            else:
                opening_labels.append(str(rr.get("name")))
        instruction = f"{' + '.join(opening_labels)} öffnen · ca. {round(recommended_duration_min)} min"
        reason_pool: list[str] = []
        # Put health/room trigger before physics to answer "why this room?".
        for c in sorted(chosen, key=lambda x: (not x.problem, -x.score)):
            if c.problem:
                for x in c.reasons:
                    if "Raumluftfeuchte" in x or "Schimmel" in x or "CO₂" in x or "steigt schnell" in x:
                        reason_pool.append(f"{c.name}: {x}")
                        break
        if is_pair:
            reason_pool.append("Die konfigurierte Fensterkombination ermöglicht schnellen Querlüftungseffekt")
        driest = max(chosen, key=lambda c: c.delta)
        if driest.delta > 0:
            reason_pool.append(f"Außen-/Referenzluft ist bis zu {driest.delta:.1f} g/m³ trockener")
            reason_pool.append(f"Erwartetes Entfeuchtungspotenzial etwa {round(removed)} ml")
        if any(c.airflow >= 1.12 for c in chosen):
            reason_pool.append("Windrichtung unterstützt den Luftwechsel")
        secondary = "Danach neu bewerten; FreshAirIQ meldet, sobald Schließen sinnvoll ist."
        goal_labels = {"humidity":"Entfeuchtung", "co2":"CO₂/Luftqualität", "temperature":"Temperaturkomfort"}
        open_goal_labels=[]
        for rr in selected_rooms:
            for gg in _open_achievable_goals(rr):
                label=goal_labels.get(str(gg.get("id")), str(gg.get("id")))
                if label not in open_goal_labels: open_goal_labels.append(label)
        if open_goal_labels:
            reason_pool.insert(0, "Aktuell erreichbar: " + ", ".join(open_goal_labels))
        summary = ("Die ausgewählte Aktion verbessert die aktuell erreichbaren Lüftungsziele unter Berücksichtigung von Prioritäten und Schutzgrenzen."
                   if open_goal_labels else
                   "Die ausgewählte Aktion liefert aktuell den besten Mix aus Feuchtewirkung, Raumrisiko und Lüftungsaufwand.")
        return result("ventilate", "ventilate", title, instruction,
                      summary,
                      selected=selected_rooms, reasons=reason_pool, severity="good",
                      duration=recommended_duration_min, removed=removed, secondary=secondary)

    # A room can be humid/problematic while ventilation is still physically
    # not worthwhile yet. Explain that state instead of selecting that room just
    # because it has the highest problem score.
    deferred_problem_rooms = []
    for r, urgent, reasons, severity in problem_rooms:
        key = str(r.get("key", ""))
        cand = candidate_by_key.get(key)
        if cand and (
            not house_physics_favourable
            or cand.potential_ml < room_threshold(r)
        ):
            deferred_problem_rooms.append((r, cand, reasons, severity))
    if deferred_problem_rooms and not chosen:
        r, cand, reasons, severity = max(deferred_problem_rooms, key=lambda x: x[3])
        name = str(r.get("name", r.get("key", "Raum")))
        why = list(reasons)
        if not house_physics_favourable:
            why.append(
                f"Hausweit ist der aktuelle Lüftungseffekt ungünstig ({round(total_potential_ml):+d} ml)"
            )
        why.append(
            f"{name}: aktuell nur etwa {round(cand.potential_ml)} ml sinnvoll entfernbar "
            f"(Mindestnutzen {round(room_threshold(r))} ml)"
        )
        return result(
            "wait", "wait", "Aktuell keine Lüftungsaktion", "Keine Aktion erforderlich",
            "Ein auffälliger Raum wird weiter überwacht; aktuell ist daraus noch keine sinnvolle Lüftungsaktion ableitbar.",
            selected=[],
            reasons=why,
            severity="warning",
            secondary=f"{name} bleibt intern priorisiert und wird bei verbessertem Lüftungsnutzen erneut bewertet.",
        )

    # If reference/outdoor air is wetter than the monitored rooms and no room
    # is a useful ventilation candidate, say so explicitly.  Preserve the signed
    # learned forecast: negative physical effect means moisture would be added.
    house_airing_effect = sum(_f(r.get("realistic_potential_ml", 0.0)) for r in valid)
    if not candidates and house_airing_effect < -20.0:
        gain = abs(round(house_airing_effect))
        return result("wait", "moisture_gain", "Jetzt nicht lüften", "Fenster geschlossen lassen",
                      f"Außen-/Referenzluft ist aktuell feuchter; Lüften würde voraussichtlich etwa +{gain} ml Feuchtigkeit eintragen.",
                      reasons=[f"Prognose für ca. {round(recommended_duration_min)} min: +{gain} ml möglicher Feuchteeintrag"],
                      severity="warning", secondary="FreshAirIQ prüft laufend, wann die Außenluft wieder zum Entfeuchten geeignet ist.")

    # No useful action is possible. Explain the most important unresolved room
    # problem instead of dumping every room state into the main recommendation.
    if blocked_problem_rooms:
        # While no ventilation session is running, an unavailable room goal is
        # not an instruction to "avoid ventilating this room".  A room-specific
        # negative recommendation is only actionable after an opening exists
        # (handled by the active/closing branches above).  Keep the idle state
        # house-scoped; genuine urgent limits already enter the candidate path
        # above and may still produce a positive targeted ventilation action.
        r, urgent, problem_reasons, _ = max(blocked_problem_rooms, key=lambda x: x[3])
        more = max(len(blocked_problem_rooms) - 1, 0)
        delta = _f(r.get("delta_g_m3"))
        if delta <= 0:
            why = "Außen-/Referenzluft ist gleich feucht oder feuchter; aktuell ergibt sich daraus keine sinnvolle Lüftungsaktion."
        else:
            why = f"Der Feuchteunterschied von {delta:.1f} g/m³ ist für eine sinnvolle Lüftungsaktion aktuell noch zu klein."
        extra = f" {more + 1} auffällige Räume werden weiter überwacht." if more else " Der auffällige Raum wird weiter überwacht."
        return result("wait", "wait", "Aktuell keine Lüftungsaktion", "Fenster geschlossen lassen",
                      "FreshAirIQ erkennt derzeit keinen ausreichend sinnvollen Lüftungsschritt." + extra,
                      selected=[], reasons=[why], severity="warning",
                      secondary="Sobald ein Lüftungsziel sinnvoll erreichbar oder eine Schutzgrenze erreicht ist, meldet FreshAirIQ die passende Aktion.")

    # Night forecast is advisory: only mention it when there is no immediate action.
    if night_forecast_ml >= max(250.0, threshold_ml * 0.35) and total_potential_ml >= max(80.0, threshold_ml * 0.25):
        return result("prepare", "wait", "Später vorlüften einplanen", "Aktuell noch warten",
                      f"Bis zum Nachtende werden etwa +{round(night_forecast_ml)} ml Feuchtigkeit erwartet.",
                      reasons=["Momentan ist noch keine ausreichend lohnende Lüftungsaktion erreicht"], severity="neutral",
                      secondary="Vor dem Nachtfenster erneut prüfen.")

    return result("okay", "okay", "Keine Lüftung nötig", "Fenster geschlossen lassen",
                  "Aktuell gibt es keine raum- oder hausweite Lüftungsaktion mit ausreichendem Nutzen.",
                  reasons=[f"Hauspotenzial {round(total_potential_ml)} ml · Schwelle {round(threshold_ml)} ml"], severity="neutral")
