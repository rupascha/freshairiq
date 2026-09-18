"""Component-level learning maturity for FreshAirIQ.

This module is intentionally descriptive.  It summarizes the evidence already
held by the existing adaptive subsystems; it does not alter any learned value,
threshold or forecast coefficient.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _status(maturity: float, samples: int, target_samples: int = 1, *, observation_only: bool = False, quality_percent: float | None = None) -> str:
    if samples <= 0:
        return "Beobachtet noch" if observation_only else "Grundschätzung"
    # High labels require both evidence depth and, where available, measured
    # quality. Sample volume alone must never imply a perfected model.
    evidence_ratio = samples / max(target_samples, 1)
    if maturity >= 92 and evidence_ratio >= 1.0 and (quality_percent is None or quality_percent >= 85):
        return "Auf deine Bedürfnisse optimiert"
    if maturity >= 78 and evidence_ratio >= 0.75 and (quality_percent is None or quality_percent >= 70):
        return "Sehr gut eingelernt"
    if maturity >= 62:
        return "Eingelernt"
    if maturity >= 45:
        return "Bestätigt"
    if maturity >= 28:
        return "Muster erkannt"
    if maturity >= 12:
        return "Beobachtet"
    return "Grundmodell"


def _component(
    key: str,
    label: str,
    samples: int,
    maturity: float,
    target_samples: int,
    detail: str,
    *,
    description: str,
    observation_only: bool = False,
    quality_percent: float | None = None,
    evidence_label: str = "Proben",
    evidence_text: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Independent evidence depth is a ceiling for every component. Internal
    # subsystem maturity may describe convergence, but convergence after only a
    # few observations must not be presented as broad real-world maturity.
    evidence_cap = min(max(int(samples), 0) / max(int(target_samples), 1), 1.0) * 100.0
    maturity = round(_bounded(min(maturity, evidence_cap)), 1)
    row: dict[str, Any] = {
        "key": key,
        "label": label,
        "samples": max(0, int(samples)),
        "target_samples": max(1, int(target_samples)),
        "maturity_percent": maturity,
        "status": _status(maturity, int(samples), int(target_samples), observation_only=observation_only, quality_percent=quality_percent),
        "description": description,
        "detail": detail,
        "observation_only": observation_only,
        "evidence_label": evidence_label,
        "evidence_text": evidence_text,
    }
    if extra:
        row.update(extra)
    if quality_percent is not None:
        row["quality_percent"] = round(_bounded(quality_percent), 1)
    return row


def build_learning_components_status(
    rooms: dict[str, dict[str, Any]] | list[dict[str, Any]],
    store_data: dict[str, Any],
    *,
    forecast_backtest: dict[str, Any] | None = None,
    post_close_stabilization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable, UI-ready learning overview for every adaptive component."""
    values = list(rooms.values()) if isinstance(rooms, dict) else list(rooms or [])
    valid = [r for r in values if isinstance(r, dict) and r.get("calculation_enabled", True)]
    n = max(len(valid), 1)

    def _unique_dates(field: str) -> set[str]:
        out: set[str] = set()
        for room in valid:
            raw = room.get(field)
            if isinstance(raw, list):
                out.update(str(x) for x in raw if x)
        return out

    room_samples = sum(int(_num(r.get("learning_samples"))) for r in valid)
    # Intelligence 2.0 deliberately requires a broad evidence base. A handful
    # of similar ventilations must no longer look like a finished model.
    room_maturity = sum(min(_num(r.get("learning_samples")) / 80.0, 1.0) for r in valid) / n * 100.0
    stable_rooms = sum(1 for r in valid if int(_num(r.get("learning_samples")))  >= 50)
    room_days = len(_unique_dates("learning_observation_dates"))
    room_time_cap = min(room_days / 45.0, 1.0) * 100.0
    room_maturity = min(room_maturity, room_time_cap)
    room_detail = f"{stable_rooms}/{len(valid)} Räume stabil · {room_days} unterschiedliche Lerntage · gelernter Luftwechsel je Raum"

    live_forecast_samples = sum(int(_num(r.get("forecast_observation_samples"))) for r in valid)
    live_forecast_maturity = (
        sum(
            min(
                min(_num(r.get("forecast_observation_samples")) / 60.0, 1.0),
                min(_num(r.get("learning_samples")) / 25.0, 1.0),
            )
            for r in valid
        ) / n * 100.0
    )
    live_forecast_stable = sum(1 for r in valid if int(_num(r.get("forecast_observation_samples")))  >= 40)
    live_forecast_maturity = min(live_forecast_maturity, min(room_days / 30.0, 1.0) * 100.0)
    live_forecast_detail = (
        f"{live_forecast_stable}/{len(valid)} Räume eingelernt · {room_days} unterschiedliche Lerntage · korrigiert Feuchte- und Temperaturtrend während laufender Lüftungen"
    )

    feedback_samples = sum(int(_num(r.get("outcome_feedback_samples"))) for r in valid)
    feedback_maturity = sum(min(_num(r.get("outcome_feedback_samples")) / 80.0, 1.0) for r in valid) / n * 100.0
    feedback_success = [
        _num(r.get("outcome_success_rate"))
        for r in valid if int(_num(r.get("outcome_feedback_samples"))) > 0
    ]
    mean_feedback_success = sum(feedback_success) / len(feedback_success) if feedback_success else None
    feedback_detail = (
        f"Prognose ↔ Realität · mittlere Trefferquote {mean_feedback_success:.0f} %"
        if mean_feedback_success is not None else "Wartet auf vergleichbare abgeschlossene Lüftungen"
    )

    shadow_samples = sum(int(_num(r.get("shadow_learning_total_samples"))) for r in valid)
    shadow_promotions = sum(int(_num(r.get("shadow_learning_promotions"))) for r in valid)
    shadow_rollbacks = sum(int(_num(r.get("shadow_learning_rollbacks"))) for r in valid)
    shadow_guarded_rooms = sum(1 for r in valid if bool(r.get("shadow_rollback_active")))
    shadow_maturity = sum(min(_num(r.get("shadow_learning_total_samples")) / 80.0, 1.0) for r in valid) / n * 100.0
    shadow_detail = (
        f"{shadow_samples} Realvergleiche · {shadow_promotions} Übernahmen · {shadow_rollbacks} automatische Rollbacks"
        + (f" · {shadow_guarded_rooms} Räume im Rollback-Schutz" if shadow_guarded_rooms else "")
    )

    routine_samples = sum(int(_num(r.get("routine_source_samples"))) for r in valid)
    routine_maturity_values = [_num(r.get("routine_maturity")) for r in valid]
    routine_model_maturity = sum(routine_maturity_values) / n if valid else 0.0
    routine_days_set: set[str] = set()
    for r in valid:
        dates = r.get("routine_observation_dates")
        if isinstance(dates, list):
            routine_days_set.update(str(x) for x in dates if x)
    routine_days = len(routine_days_set)
    # Repeated samples on the same day improve a bucket but cannot simulate
    # independent daily experience. Ninety observed days are required for full
    # routine evidence.
    routine_maturity = min(routine_model_maturity, min(routine_days / 90.0, 1.0) * 100.0)
    routine_detail = f"{routine_samples} brauchbare Messpunkte · {routine_days} unterschiedliche Tage beobachtet"

    seasonal_samples = sum(int(_num(r.get("seasonal_samples"))) for r in valid)
    season_names = {"spring": "Frühling", "summer": "Sommer", "autumn": "Herbst", "winter": "Winter"}
    seasonal_period_days: dict[str, set[str]] = {}
    for r in valid:
        obs = r.get("seasonal_observation_days")
        if isinstance(obs, dict):
            for period, days in obs.items():
                if isinstance(days, list):
                    seasonal_period_days.setdefault(str(period), set()).update(str(x) for x in days if x)

    def _season_bounds(year: int, key: str) -> tuple[date, date]:
        if key == "spring": return date(year, 3, 1), date(year, 5, 31)
        if key == "summer": return date(year, 6, 1), date(year, 8, 31)
        if key == "autumn": return date(year, 9, 1), date(year, 11, 30)
        # Winter is identified by its starting year: Dec Y through Feb Y+1.
        next_year = year + 1
        leap = 29 if (next_year % 4 == 0 and (next_year % 100 != 0 or next_year % 400 == 0)) else 28
        return date(year, 12, 1), date(next_year, 2, leap)

    completed_seasons: set[str] = set()
    season_breakdown: list[dict[str, Any]] = []
    all_dates: set[date] = set()
    for raw in seasonal_period_days.values():
        for d in raw:
            try: all_dates.add(date.fromisoformat(d))
            except ValueError: pass
    for key in ("spring", "summer", "autumn", "winter"):
        best_days = 0
        full = False
        best_year = None
        for period, raw_days in seasonal_period_days.items():
            try:
                year_s, period_key = period.split(":", 1)
                year = int(year_s)
            except (ValueError, TypeError):
                continue
            if period_key != key:
                continue
            parsed = []
            for raw in raw_days:
                try: parsed.append(date.fromisoformat(raw))
                except ValueError: pass
            if not parsed:
                continue
            begin, finish = _season_bounds(year, key)
            # A season is only "fully traversed" when useful observations exist
            # near both boundaries and on at least 60 distinct days. Installing
            # mid-season therefore cannot retrospectively complete that season.
            near_start = min(parsed) <= begin.fromordinal(begin.toordinal() + 7)
            near_end = max(parsed) >= finish.fromordinal(finish.toordinal() - 7)
            this_full = len(set(parsed)) >= 60 and near_start and near_end
            if len(set(parsed)) > best_days:
                best_days, best_year = len(set(parsed)), year
            full = full or this_full
        if full:
            completed_seasons.add(key)
        season_breakdown.append({"key": key, "label": season_names[key], "optimized": full, "observed_days": best_days, "year": best_year})
    calendar_span_days = (max(all_dates) - min(all_dates)).days + 1 if len(all_dates) >= 2 else (1 if all_dates else 0)
    seasonal_maturity = min(len(completed_seasons) / 4.0, 1.0) * 100.0
    # Highest seasonal maturity is impossible before at least a full year of
    # real calendar coverage, even if all counters are artificially huge.
    if calendar_span_days < 365:
        seasonal_maturity = min(seasonal_maturity, min(calendar_span_days / 365.0, 1.0) * 91.9)
    seasonal_detail = " · ".join(f"{x['label']}: {'optimiert' if x['optimized'] else str(x['observed_days']) + ' Tage'}" for x in season_breakdown)

    strategy_samples = sum(int(_num(r.get("strategy_samples"))) for r in valid)
    strategy_outcomes = sum(int(_num(r.get("strategy_outcome_samples"))) for r in valid)
    strategy_maturity_values = [
        min(_num(r.get("strategy_maturity")), min(_num(r.get("strategy_outcome_samples")) / 40.0, 1.0) * 100.0)
        for r in valid
    ]
    strategy_maturity = sum(strategy_maturity_values) / n if valid else 0.0
    strategy_days = len(_unique_dates("strategy_observation_dates"))
    strategy_maturity = min(strategy_maturity, min(strategy_days / 45.0, 1.0) * 100.0)
    strategy_detail = f"{strategy_samples} Strategieentscheidungen · {strategy_outcomes} unabhängige Ergebnisvergleiche · {strategy_days} unterschiedliche Tage"

    recommendation_opportunities = sum(int(_num(r.get("behaviour_recommendation_opportunities"))) for r in valid)
    duration_samples = sum(int(_num(r.get("behaviour_duration_samples"))) for r in valid)
    personal_context_maturity = (
        sum(
            min(
                min(_num(r.get("behaviour_recommendation_opportunities")) / 60.0, 1.0),
                min(_num(r.get("behaviour_duration_samples")) / 60.0, 1.0),
            )
            for r in valid
        ) / n * 100.0
    )
    personal_days = len(_unique_dates("personal_context_observation_dates"))
    personal_context_maturity = min(personal_context_maturity, min(personal_days / 60.0, 1.0) * 100.0)
    followed_total = sum(int(_num(r.get("behaviour_recommendation_followed"))) for r in valid)
    follow_rate = (100.0 * followed_total / recommendation_opportunities) if recommendation_opportunities > 0 else None
    personal_context_detail = (
        f"{recommendation_opportunities} Empfehlungschancen · {follow_rate:.0f} % umgesetzt · {duration_samples} Lüftungsdauern · {personal_days} unterschiedliche Tage"
        if follow_rate is not None
        else f"Noch keine Empfehlungschancen · {duration_samples} Lüftungsdauern · {personal_days} unterschiedliche Tage"
    )

    night_samples = int(_num(store_data.get("night_model_samples")))
    night_dates_raw = store_data.get("night_observed_dates")
    night_dates = sorted(set(str(x) for x in night_dates_raw if x)) if isinstance(night_dates_raw, list) else []
    night_count = len(night_dates)
    night_maturity = min(night_count / 120.0, 1.0) * 100.0
    night_span_days = 0
    if night_dates:
        try:
            parsed_nights = [date.fromisoformat(x) for x in night_dates]
            night_span_days = (max(parsed_nights) - min(parsed_nights)).days + 1
        except ValueError:
            night_span_days = 0
    night_detail = f"{night_samples} Messupdates aus {night_count} unterschiedlichen Nächten · Zeitraum {night_span_days} Tage"

    house_samples = int(_num(store_data.get("house_strategy_samples")))
    house_dates_raw = store_data.get("house_strategy_observation_dates")
    house_dates = set(str(x) for x in house_dates_raw if x) if isinstance(house_dates_raw, list) else set()
    house_days = len(house_dates)
    house_maturity = min(min(house_samples / 150.0, 1.0), min(house_days / 45.0, 1.0)) * 100.0
    house_detail = f"{house_samples} Hauslüftungen über {house_days} unterschiedliche Tage · bewertet Strategieergebnisse über mehrere Bedingungen"

    backtest = forecast_backtest or {}
    reliability = backtest.get("reliability") or {}
    validation_samples = int(_num(backtest.get("room_sample_count")))
    validation_days = int(_num(backtest.get("distinct_validation_days")))
    evidence = min(min(validation_samples / 100.0, 1.0), min(validation_days / 30.0, 1.0)) * 100.0
    reliability_score = reliability.get("score_percent")
    validation_detail = (
        f"Modellzuverlässigkeit {float(reliability_score):.0f} % · MAE {_num((backtest.get('overall') or {}).get('moisture_mae_ml')):.0f} ml · {validation_days} Validierungstage"
        if reliability_score is not None and validation_samples > 0
        else "Sammelt saubere Startprognose-vs.-Messung-Vergleiche"
    )

    stabilization = post_close_stabilization or {}
    stabilization_samples = int(_num(stabilization.get("valid_observations")))
    stabilization_days = int(_num(stabilization.get("distinct_observation_days")))
    stabilization_maturity = min(min(stabilization_samples / 50.0, 1.0), min(stabilization_days / 20.0, 1.0)) * 100.0
    buffer_fraction = stabilization.get("average_buffer_fraction_percent")
    stabilization_detail = (
        f"Ø Feuchtepuffer {float(buffer_fraction):.0f} % nach dem Schließen · {stabilization_days} unterschiedliche Tage"
        if buffer_fraction is not None and stabilization_samples > 0
        else f"Beobachtet Feuchterückstrom nach dem Schließen; {stabilization_days} unterschiedliche Tage"
    )

    components = [
        _component("room_physics", "Raumphysik", room_samples, room_maturity, max(len(valid), 1) * 80, room_detail,
                   description="Lernt den realen Luftwechsel und die raumspezifische Lüftungswirkung."),
        _component("live_forecast", "Live-Prognosemodell", live_forecast_samples, live_forecast_maturity, max(len(valid), 1) * 60, live_forecast_detail,
                   description="Lernt aus laufenden Messungen, wie stark die physikalische Feuchte- und Temperaturprognose live korrigiert werden muss."),
        _component("forecast_feedback", "Prognosefeedback", feedback_samples, feedback_maturity, max(len(valid), 1) * 80, feedback_detail,
                   description="Vergleicht eingefrorene Prognosen mit belastbaren realen Ergebnissen.", quality_percent=mean_feedback_success),
        _component("shadow_learning", "Learning 3.0 · Shadow-Modelle", shadow_samples, shadow_maturity, max(len(valid), 1) * 80, shadow_detail,
                   description="Lässt alternative Feuchte-Kalibrierungen parallel gegen reale Ergebnisse antreten und übernimmt sie nur bei wiederholt messbarer Verbesserung."),
        _component("routines", "Tagesroutinen", routine_days, routine_maturity, 90, routine_detail,
                   description="Erkennt wiederkehrende Feuchte- und Nutzungsmuster über den Tagesverlauf."),
        _component("seasonality", "Saisonalität", len(completed_seasons), seasonal_maturity, 4, seasonal_detail,
                   description="Lernt jede Jahreszeit separat. Optimiert erst nach vollständig beobachtetem Frühling, Sommer, Herbst und Winter sowie mindestens einem Jahr Kalenderabdeckung."),
        _component("user_strategy", "Nutzerstrategie", strategy_outcomes, strategy_maturity, max(len(valid), 1) * 40, strategy_detail,
                   description="Lernt, welche konkreten Lüftungsstrategien umgesetzt werden und wie deren Ergebnisse ausfallen."),
        _component("personal_context", "Persönlicher Kontext", duration_samples, personal_context_maturity, max(len(valid), 1) * 60, personal_context_detail,
                   description="Lernt Umsetzungsgewohnheiten des Haushalts; explizite Komfort- und Energiepräferenzen wirken unabhängig davon sofort."),
        _component("night_model", "Nachtmodell", night_count, night_maturity, 120, night_detail,
                   description="Passt die Nachtprognose an reale Feuchteentwicklung und Belegung an. Für die Reife zählt jede Nacht höchstens einmal."),
        _component("house_strategy", "Hausstrategie", house_samples, house_maturity, 150, house_detail,
                   description="Bewertet hausweite Lüftungsentscheidungen statt nur einzelne Räume."),
        _component("forecast_validation", "Prognosevalidierung", validation_samples, evidence, 100, validation_detail,
                   description="Misst die objektive Prognosegüte, getrennt vom adaptiven Lernmodell.", quality_percent=_num(reliability_score) if reliability_score is not None else None),
        _component("post_close", "Feuchtepuffer", stabilization_samples, stabilization_maturity, 50, stabilization_detail,
                   description="Vermisst Nachstabilisierung und hygroskopischen Feuchterückstrom.", observation_only=True),
    ]

    # UI evidence units: raw polling samples are deliberately not presented as
    # independent experience for temporal models. Applied after construction so
    # older test/plugin wrappers around _component remain compatible.
    for row in components:
        key = row.get("key")
        if key == "routines":
            row.update({"evidence_label": "Tage", "evidence_text": f"{routine_days} unterschiedliche Tage · Ziel 90"})
        elif key == "seasonality":
            row.update({"evidence_label": "Jahreszeiten", "evidence_text": f"{len(completed_seasons)}/4 Jahreszeiten vollständig · {calendar_span_days}/365 Tage Kalenderabdeckung", "season_breakdown": season_breakdown, "calendar_span_days": calendar_span_days, "raw_samples": seasonal_samples})
        elif key == "night_model":
            row.update({"evidence_label": "Nächte", "evidence_text": f"{night_count} unterschiedliche Nächte · Ziel 120 ({night_count}/120)", "raw_samples": night_samples})
        elif key in {"forecast_feedback", "forecast_validation"}:
            row["evidence_label"] = "Vergleiche"
            if key == "forecast_validation":
                row["evidence_text"] = f"{validation_samples} Vergleiche ({validation_samples}/100) · {validation_days} unterschiedliche Tage ({validation_days}/30 Validierungstage)"
        elif key == "shadow_learning":
            row["evidence_label"] = "Realvergleiche"
        elif key == "user_strategy":
            row.update({"evidence_label": "Ergebnisvergleiche", "evidence_text": f"{strategy_outcomes} Ergebnisvergleiche · {strategy_days} unterschiedliche Tage ({strategy_days}/45)"})
        elif key == "personal_context":
            row.update({"evidence_label": "Lüftungen", "evidence_text": f"{duration_samples} Lüftungen · {personal_days} unterschiedliche Tage ({personal_days}/60)"})
        elif key == "live_forecast":
            row.update({"evidence_label": "Messpunkte", "evidence_text": f"{live_forecast_samples} Messpunkte · {room_days} unterschiedliche Lerntage ({room_days}/30)"})
        elif key == "room_physics":
            row.update({"evidence_label": "Lernlüftungen", "evidence_text": f"{room_samples} Lernlüftungen · {room_days} unterschiedliche Lerntage ({room_days}/45)"})
        elif key == "post_close":
            row.update({"evidence_label": "Schließbeobachtungen", "evidence_text": f"{stabilization_samples} Beobachtungen · {stabilization_days} unterschiedliche Tage ({stabilization_days}/20)"})
        elif key == "house_strategy":
            row.update({"evidence_label": "Lüftungen", "evidence_text": f"{house_samples} Hauslüftungen · {house_days} unterschiedliche Tage ({house_days}/45)"})

    # Overall learning maturity is evidence depth only; it is deliberately not
    # presented as prediction accuracy.
    adaptive = [c for c in components if not c["observation_only"]]
    overall_raw = sum(float(c["maturity_percent"]) for c in adaptive) / len(adaptive) if adaptive else 0.0
    by_key = {c["key"]: c for c in components}
    core_keys = ("room_physics", "live_forecast", "forecast_feedback", "forecast_validation")
    core_floor = min((float(by_key[k]["maturity_percent"]) for k in core_keys), default=0.0)
    validation_quality = by_key["forecast_validation"].get("quality_percent")
    # A high average must not hide one immature core model. Core evidence has
    # equal weight, and objective validation imposes a hard ceiling on claims
    # of maturity. This prevents a burst of similar samples from looking like
    # a fully personalised model.
    overall = 0.50 * overall_raw + 0.50 * core_floor
    if validation_samples < 10:
        overall = min(overall, 27.9)
    elif validation_samples < 25:
        overall = min(overall, 44.9)
    elif validation_samples < 50:
        overall = min(overall, 61.9)
    elif validation_samples < 100:
        overall = min(overall, 77.9)
    elif validation_quality is not None and float(validation_quality) < 70:
        overall = min(overall, 77.9)
    personal = float(by_key["personal_context"]["maturity_percent"])
    if overall < 12:
        stage = ("grundmodell", "Grundmodell")
    elif overall < 28:
        stage = ("beobachtet", "Beobachtet")
    elif overall < 45:
        stage = ("muster_erkannt", "Muster erkannt")
    elif overall < 62:
        stage = ("bestaetigt", "Bestätigt")
    elif overall < 78:
        stage = ("eingelernt", "Eingelernt")
    elif overall < 92:
        stage = ("sehr_gut_eingelernt", "Sehr gut eingelernt")
    elif (
        personal >= 90
        and float(by_key["routines"]["maturity_percent"]) >= 90
        and float(by_key["night_model"]["maturity_percent"]) >= 90
        and float(by_key["seasonality"]["maturity_percent"]) >= 100
        and validation_samples >= 100
        and core_floor >= 90
        and validation_quality is not None
        and float(validation_quality) >= 85
    ):
        stage = ("auf_beduerfnisse_optimiert", "Auf deine Bedürfnisse optimiert")
    else:
        stage = ("sehr_gut_eingelernt", "Sehr gut eingelernt")
    return {
        "version": "v5",
        "overall_maturity_percent": round(overall, 1),
        "raw_maturity_percent": round(overall_raw, 1),
        "core_evidence_floor_percent": round(core_floor, 1),
        "stage_key": stage[0],
        "stage_label": stage[1],
        "personal_optimization_ready": stage[0] == "auf_beduerfnisse_optimiert",
        "component_count": len(components),
        "components": components,
        "note": "Intelligence 2.0 trennt Datenmenge von unabhängiger Erfahrung. Zeitmodelle reifen über unterschiedliche Tage, Nächte und vollständig durchlaufene Jahreszeiten; hohe Pollingraten können Reife nicht beschleunigen. Learning 3.0 behält Shadow- und Rollback-Schutz bei.",
    }
