"""FreshAirIQ Unified Decision Brain.

This module turns the existing intelligence layers into one user-facing decision.
It does not create another independent model. It reconciles the current physical
recommendation, short-term simulation, multi-hour planning, learned routines,
seasonality and house strategy into a single explainable output.
"""
from __future__ import annotations
from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _unique(values: list[str], limit: int = 5) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _room_names(keys: list[str], rooms: dict[str, dict[str, Any]]) -> list[str]:
    return [str(rooms[k].get("name") or k) for k in keys if k in rooms]


def _risk_reason(room: dict[str, Any], options: dict[str, Any]) -> str | None:
    name = str(room.get("name") or "Raum")
    rh = _f(room.get("humidity"))
    surface = _f(room.get("surface_rh"))
    co2_available = bool(room.get("co2_available", room.get("co2") is not None))
    co2 = _f(room.get("co2")) if co2_available else 0.0
    high_rh = _f(options.get("high_rh"), 68.0)
    mould = _f(options.get("mould_warn_surface_rh"), 80.0)
    co2_warn = _f(options.get("co2_warn"), 1000.0)
    if surface >= mould:
        return f"{name}: Oberflächenfeuchte {round(surface)} % erhöht das Schimmelrisiko"
    if co2_available and co2 >= co2_warn:
        return f"{name}: CO₂ liegt bei etwa {round(co2)} ppm"
    if rh >= high_rh:
        return f"{name}: Raumluftfeuchte liegt bei {round(rh)} %"
    return None


def _find_option(options: list[dict[str, Any]], oid: str) -> dict[str, Any] | None:
    return next((x for x in options if str(x.get("id")) == str(oid)), None)


def build_unified_decision(
    recommendation: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
    options: dict[str, Any],
    *,
    cross_active: bool = False,
    night_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(recommendation or {})
    kind = str(out.get("kind") or "okay")
    room_keys = [str(k) for k in (out.get("room_keys") or []) if str(k) in rooms]
    names = _room_names(room_keys, rooms)

    short_options = list(out.get("simulated_options") or [])
    plan = out.get("day_night_plan") if isinstance(out.get("day_night_plan"), dict) else {}
    long_options = list(plan.get("options") or [])
    short_selected = _find_option(short_options, str(out.get("selected_option_id") or ""))
    plan_selected = _find_option(long_options, str(plan.get("selected_option_id") or ""))
    now_short = _find_option(short_options, "now")
    now_long = _find_option(long_options, "now")

    confidence = max(
        _f(out.get("forecast_confidence")),
        _f(short_selected.get("confidence") if short_selected else 0),
        _f(plan.get("confidence")),
    )
    why: list[str] = []
    for key in room_keys:
        reason = _risk_reason(rooms[key], options)
        if reason:
            why.append(reason)

    # Strongest physical opportunity among selected rooms.
    selected_rooms = [rooms[k] for k in room_keys if k in rooms]
    if selected_rooms:
        delta = max((_f(r.get("delta_g_m3")) for r in selected_rooms), default=0.0)
        if delta > 0.4:
            why.append(f"Außen-/Referenzluft ist bis zu {delta:.1f} g/m³ trockener")
        potential = sum(max(_f(r.get("realistic_potential_ml", r.get("potential_ml"))), 0.0) for r in selected_rooms)
        if potential >= 40:
            why.append(f"In den ausgewählten Räumen sind aktuell etwa {round(potential)} ml entfernbar")

    house = out.get("house_strategy") if isinstance(out.get("house_strategy"), dict) else {}
    if _f(house.get("maturity")) >= 20:
        eff = _f(house.get("efficiency_factor"), 1.0)
        if eff >= 1.08:
            why.append(f"Diese Lüftungsstrategie war bisher rund {round((eff-1)*100)} % effizienter als dein bisheriger Lüftungsdurchschnitt")
        elif eff <= 0.92:
            why.append(f"Diese Lüftungsstrategie war bisher rund {round((1-eff)*100)} % weniger effizient als dein bisheriger Lüftungsdurchschnitt")

    comparison: dict[str, Any] = {}
    alternative = ""
    decision_label = ""
    action_line = str(out.get("instruction") or "")
    headline = str(out.get("title") or "")
    summary = str(out.get("summary") or "")

    if kind == "ventilate":
        headline = "Jetzt ist das beste Lüftungsfenster"
        if cross_active and len(names) >= 2:
            decision_label = "JETZT QUERLÜFTEN"
            action_line = f"{' + '.join(names)} · etwa {round(_f(out.get('duration_min')))} min"
        else:
            decision_label = "JETZT LÜFTEN"
            action_line = f"{' + '.join(names) if names else 'Empfohlene Räume'} · etwa {round(_f(out.get('duration_min')))} min"

        # Explain why now beats waiting, if the matrix actually has alternatives.
        future = next((x for x in short_options if str(x.get("id","")).startswith("wait_")), None)
        if future and now_short:
            best_future = max(
                (x for x in short_options if str(x.get("id","")).startswith("wait_")),
                key=lambda x: _f(x.get("score")), default=None
            )
            if best_future:
                comparison = {
                    "now_score": round(_f(now_short.get("score")),1),
                    "alternative_score": round(_f(best_future.get("score")),1),
                    "alternative_label": str(best_future.get("label") or ""),
                }
                alternative = f"{best_future.get('label')}: voraussichtlich {round(_f(best_future.get('removed_ml')))} ml"
        summary = (
            "FreshAirIQ bewertet das aktuelle Fenster aus Feuchtewirkung, Wetter, Raumrisiko, "
            "Temperaturverlust und gelernten Hausdaten als die beste verfügbare Option."
        )

    elif kind == "wait":
        delay = plan.get("selected_delay_min")
        selected = plan_selected or short_selected
        if selected and str(selected.get("id","")).startswith(("in_","wait_")):
            mins = int(_f(selected.get("delay_min"), delay or 0))
            when = f"in etwa {mins//60} h" if mins >= 60 and mins % 60 == 0 else f"in etwa {mins} min"
            headline = "Ein besseres Lüftungsfenster kommt später"
            decision_label = "NOCH WARTEN"
            action_line = f"{when.capitalize()} erneut bewerten"
            future_ml = round(_f(selected.get("removed_ml", selected.get("projected_potential_ml"))))
            now_ml = round(_f(now_short.get("removed_ml") if now_short else (now_long or {}).get("projected_potential_ml")))
            if future_ml > 0:
                why.append(f"Für das spätere Fenster werden etwa {future_ml} ml Wirkung erwartet")
            if now_ml > 0 and future_ml > now_ml:
                why.append(f"Das sind etwa {future_ml-now_ml} ml mehr als jetzt")
            comparison = {
                "now_ml": max(now_ml,0), "future_ml": max(future_ml,0),
                "delay_min": mins, "alternative_label": str(selected.get("label") or "")
            }
            alternative = f"Jetzt wären etwa {max(now_ml,0)} ml möglich"
            summary = (
                "Warten ist hier keine passive Standardantwort: Die Simulation erwartet ein messbar "
                "günstigeres Zeitfenster, ohne dass das aktuelle Gesundheitsrisiko ein sofortiges Lüften erzwingt."
            )
        elif str(out.get("status")) == "moisture_gain":
            headline = "Außenluft ist momentan die schlechtere Wahl"
            decision_label = "FENSTER GESCHLOSSEN LASSEN"
            summary = str(out.get("summary") or "Lüften würde aktuell zusätzliche Feuchtigkeit eintragen.")
        else:
            headline = str(out.get("title") or "Noch warten")
            decision_label = "NOCH WARTEN"

    elif kind == "prepare":
        headline = "Jetzt Feuchtepuffer schaffen"
        decision_label = "VORLÜFTEN"
        action_line = str(out.get("instruction") or "")
        summary = (
            "FreshAirIQ erwartet in Kürze eine typische Feuchtezunahme. Die aktuelle Außenluft ist bereits "
            "geeignet, deshalb ist kurzes Vorlüften sinnvoller als erst auf den späteren Anstieg zu reagieren."
        )

    elif kind == "continue":
        headline = "Lüftung läuft – FreshAirIQ optimiert live"
        decision_label = "WEITERLÜFTEN"
        target = _f(out.get("live_coach_target_min"), _f(out.get("duration_min")))
        remain = _f(out.get("live_coach_remaining_min"))
        action_line = f"Ziel etwa {target:g} min"
        if remain > 0:
            action_line += f" · noch ca. {round(remain)} min"
        summary = str(out.get("live_coach_reason") or out.get("summary") or "Die laufende Lüftung wird anhand der realen Wirkung weiter bewertet.")

    elif kind == "close":
        headline = "Der sinnvolle Lüftungspunkt ist erreicht"
        decision_label = "JETZT SCHLIESSEN"
        action_line = f"{' + '.join(names) if names else 'Geöffnete Fenster'} schließen"
        summary = "Die zusätzliche Wirkung nimmt gegenüber Temperaturverlust und Feuchteziel nicht mehr ausreichend zu."

    elif kind == "pollen_wait":
        headline = "Lüften wäre sinnvoll – Pollen sprechen dagegen"
        decision_label = "VERSCHIEBEN"
        summary = str(out.get("summary") or "Die Pollenregel hat die ansonsten sinnvolle Lüftung aktuell überstimmt.")

    elif kind == "sensor":
        headline = "FreshAirIQ kann aktuell nicht zuverlässig entscheiden"
        decision_label = "SENSORDATEN PRÜFEN"
        summary = str(out.get("summary") or "Mindestens ein notwendiger Messwert ist ungültig oder nicht verfügbar.")

    elif kind == "okay" and str(out.get("status") or "") == "passive_open_monitor":
        # A long, thermally stable opening is a deliberate monitor state, not an
        # ordinary idle/closed-window state. Keep that distinction visible all
        # the way through the Decision Brain so the UI cannot contradict the
        # actually open contact with "Fenster geschlossen lassen".
        headline = str(out.get("title") or "Daueröffnung wird überwacht")
        decision_label = "DAUER-/KIPPLÜFTUNG"
        action_line = str(out.get("instruction") or "Fenster kann vorerst offen/gekippt bleiben")
        summary = (
            "FreshAirIQ behandelt die lange, stabile Öffnung als wahrscheinliche Dauer- oder Kipplüftung. "
            "Temperatur, Feuchtebilanz und Außenbedingungen werden weiter überwacht. "
            "Werden sie ungünstig, empfiehlt FreshAirIQ das Schließen."
        )
        why.insert(0, "Lange Öffnung erkannt: Temperatur und Feuchtebilanz sind derzeit stabil")

    else:
        headline = "Aktuell ist keine Lüftungsaktion nötig"
        decision_label = "WEITER BEOBACHTEN"
        action_line = "Fenster geschlossen lassen"
        if plan.get("active") and str(plan.get("selected_option_id")) != "now":
            alternative = f"Nächstes interessantes Fenster: {plan.get('selected_label')}"
        summary = (
            "Die aktuellen Risiken und das entfernbar berechnete Feuchtepotenzial rechtfertigen derzeit "
            "keine Lüftungsaktion. FreshAirIQ bewertet Wetter und Raumverlauf weiter."
        )

    # Evening/night strategy becomes the primary story only when there is no
    # stronger immediate action. Urgent ventilation, close, pollen and sensor
    # decisions retain precedence and the night strategy remains contextual.
    ns = night_strategy if isinstance(night_strategy, dict) else {}
    if ns.get("active") and kind in {"okay", "wait"} and ns.get("action") in {"close", "open_selected", "pre_ventilate", "closed_monitor"}:
        decision_label = str(ns.get("label") or "NACHTSTRATEGIE")
        headline = str(ns.get("headline") or headline)
        action_line = str(ns.get("instruction") or action_line)
        summary = str(ns.get("summary") or summary)
        why = list(ns.get("reasons") or []) + why
        confidence = max(confidence, _f(ns.get("confidence")))
        night_names = [str(x) for x in (ns.get("selected_rooms") or []) if str(x)]
        if night_names:
            names = night_names
        out["night_strategy_primary"] = True
    elif ns.get("active"):
        out["night_strategy_primary"] = False

    # Existing engine reasons are still useful, but the new user-facing reasons
    # lead with concrete physical/learned evidence instead of engine narration.
    existing = [str(x) for x in (out.get("reasons") or []) if x]
    why = _unique(why + existing, 5)

    impact = {
        "moisture_ml": round(_f(out.get("estimated_removed_ml"))),
        "temperature_c": round(_f(out.get("expected_temperature_change_c")), 2),
        "cost": round(max(_f(out.get("estimated_reheat_cost")), 0.0), 2),
        "duration_min": round(_f(out.get("duration_min")), 1) if out.get("duration_min") is not None else None,
        "confidence": round(min(max(confidence,0.0),100.0)),
    }

    out.update({
        "title": headline,
        "instruction": action_line,
        "summary": summary,
        "reasons": why,
        "decision_brain": {
            "version": "v1",
            "decision_label": decision_label,
            "headline": headline,
            "action_line": action_line,
            "summary": summary,
            "why": why,
            "impact": impact,
            "comparison": comparison,
            "alternative": alternative,
            "selected_rooms": names,
            "short_term_options": len(short_options),
            "long_term_options": len(long_options),
            "cross_ventilation": bool(cross_active and len(names) >= 2),
            "night_strategy": ns,
            "night_strategy_primary": bool(out.get("night_strategy_primary", False)),
        },
        "decision_brain_engine": "v1",
    })
    return out
