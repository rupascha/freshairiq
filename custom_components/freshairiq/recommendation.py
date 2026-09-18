"""FreshAirIQ Recommendation Engine v2.

Turns room diagnostics into one prioritised, actionable house recommendation.
The engine is deliberately pure so it can be unit-tested without Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable


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
) -> dict[str, Any]:
    """Compose the single best action for the home at this moment."""
    valid = [r for r in rooms.values() if r.get("calculation_enabled", True) and r.get("data_quality") == "ok"]
    bad = [r for r in rooms.values() if r.get("calculation_enabled", True) and r.get("data_quality") != "ok"]
    active = [r for r in valid if r.get("active")]
    closing = [r for r in active if r.get("action") == "Close" or r.get("close_recommended")]

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
        return result("continue", "ventilation_running", "Weiterlüften", f"{names} offen lassen · noch ca. {max(round(remaining),1)} min",
                      "FreshAirIQ bewertet Nutzen und Temperaturverlust während der laufenden Lüftung weiter.",
                      selected=active, reasons=reasons, severity="good", duration=remaining, removed=max(effect, 0.0))

    candidates = [_candidate(r, options, threshold_ml) for r in valid
                  if r.get("action") in {"Ventilate", "Ventilate for cooling"}
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
            if r.get("action") in {"Do not ventilate", "Wait"}:
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
    elif targeted:
        chosen = [max(targeted, key=lambda c: c.score)]
    elif house_ready and candidates:
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        # Keep the instruction simple: only add a second room when it provides
        # meaningful extra potential and is not strongly wind-disadvantaged.
        chosen = ranked[:1]
        if len(ranked) > 1 and ranked[1].potential_ml >= max(60.0, threshold_ml * 0.12) and ranked[1].airflow >= 0.8:
            chosen.append(ranked[1])

    if chosen and pollen_blocked and not any(c.urgent for c in chosen):
        names = ", ".join(c.name for c in chosen)
        return result("pollen_wait", "pollen_warning", "Lüften verschieben", "Fenster vorerst geschlossen lassen",
                      f"{names} würden von Lüftung profitieren, die aktuelle Pollenbelastung spricht aber gegen ein Öffnen.",
                      selected=[room_by_key[c.key] for c in chosen],
                      reasons=[f"Pollenindex {pollen_index:.1f} liegt über dem eingestellten Grenzwert"], severity="warning")

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
        elif any(c.urgent and any("CO₂" in reason for reason in c.reasons) for c in chosen):
            reason_pool.append(
                f"Außen-/Referenzluft ist bis zu {abs(driest.delta):.1f} g/m³ feuchter; "
                "kritisches CO₂ hat dennoch Vorrang vor dem begrenzten Feuchtenachteil"
            )
        if any(c.airflow >= 1.12 for c in chosen):
            reason_pool.append("Windrichtung unterstützt den Luftwechsel")
        secondary = "Danach neu bewerten; FreshAirIQ meldet, sobald Schließen sinnvoll ist."
        return result("ventilate", "ventilate", title, instruction,
                      "Die ausgewählte Aktion liefert aktuell den besten Mix aus Feuchtewirkung, Raumrisiko und Lüftungsaufwand.",
                      selected=selected_rooms, reasons=reason_pool, severity="good",
                      duration=recommended_duration_min, removed=removed, secondary=secondary)

    # A room can be humid/problematic while ventilation is still physically
    # not worthwhile yet. Explain that state instead of selecting that room just
    # because it has the highest problem score.
    deferred_problem_rooms = []
    for r, urgent, reasons, severity in problem_rooms:
        if urgent:
            continue
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
            "wait", "wait", "Feuchteproblem beobachten", "Noch nicht lüften",
            f"{name} benötigt Aufmerksamkeit, aber der aktuelle Lüftungsnutzen ist noch zu gering. "
            "FreshAirIQ wartet auf ein besseres Außenluftfenster.",
            selected=[],
            reasons=why,
            severity="warning",
            secondary=f"{name} bleibt priorisiert und wird bei verbessertem Lüftungsnutzen erneut bewertet.",
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
        r, urgent, problem_reasons, _ = max(blocked_problem_rooms, key=lambda x: x[3])
        more = max(len(blocked_problem_rooms) - 1, 0)
        delta = _f(r.get("delta_g_m3"))
        if delta <= 0:
            why = "Außen-/Referenzluft ist gleich feucht oder feuchter und würde das Problem nicht verbessern."
        else:
            why = f"Der Feuchteunterschied von {delta:.1f} g/m³ ist für wirksames Entfeuchten noch zu klein."
        extra = f" · {more} weitere Räume beobachten" if more else ""
        return result("wait", "wait", "Noch nicht lüften", "Fenster geschlossen lassen",
                      f"{r.get('name')}: {problem_reasons[0] if problem_reasons else 'Raumklima auffällig'}{extra}.",
                      selected=[r], reasons=[why], severity="danger" if urgent else "warning",
                      secondary="FreshAirIQ bewertet die Außenbedingungen laufend neu.")

    # Night forecast is advisory: only mention it when there is no immediate action.
    if night_forecast_ml >= max(250.0, threshold_ml * 0.35) and total_potential_ml >= max(80.0, threshold_ml * 0.25):
        return result("prepare", "wait", "Später vorlüften einplanen", "Aktuell noch warten",
                      f"Bis zum Nachtende werden etwa +{round(night_forecast_ml)} ml Feuchtigkeit erwartet.",
                      reasons=["Momentan ist noch keine ausreichend lohnende Lüftungsaktion erreicht"], severity="neutral",
                      secondary="Vor dem Nachtfenster erneut prüfen.")

    return result("okay", "okay", "Keine Lüftung nötig", "Fenster geschlossen lassen",
                  "Aktuell gibt es keine raum- oder hausweite Lüftungsaktion mit ausreichendem Nutzen.",
                  reasons=[f"Hauspotenzial {round(total_potential_ml)} ml · Schwelle {round(threshold_ml)} ml"], severity="neutral")
