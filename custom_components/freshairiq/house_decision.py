"""House-level decision rules (pure logic, no Home Assistant imports).

Extracted from the coordinator update cycle in 0.26.3.2 so the rules can be
tested directly at their thresholds. The coordinator calls these functions once
per cycle; behaviour is pinned by tests/test_coordinator_golden_master.py and
the rule boundaries by tests/test_house_decision_rules.py.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .consolidation import aggregate_close_allowed, aggregate_close_gate_ready
from .model import min_return_volume_factor


def _mean_volume_factor(rooms: list[dict[str, Any]]) -> float:
    """Average room-volume factor for aggregate close thresholds (GitHub #15)."""
    factors = [min_return_volume_factor(room.get("volume_m3") if isinstance(room, dict) else None) for room in rooms]
    return sum(factors) / len(factors) if factors else 1.0

def ventilation_threshold_decision(
    *,
    expected_daily_generation: Any,
    now: Any,
    options: Any,
    outdoor_t: Any,
    pollen: Any,
    threshold_mode: Any,
    total_water: Any,
    valid: Any,
) -> Any:
    """Phase 3: house-wide ventilation threshold (fixed / adaptive / percentage) and pollen veto."""
    threshold_reason = ""
    if threshold_mode == "fixed_ml":
        ventilation_threshold = float(options.get("min_potential_total_ml", 500))
        threshold_reason = "fixed_ml"
    elif threshold_mode == "percent_total_water":
        ventilation_threshold = total_water * float(options.get("min_potential_percent_total_water", 10.0)) / 100.0
        threshold_reason = "percent_total_water"
    else:
        # Aim for roughly four meaningful ventilation opportunities per day
        # (inside the requested 3–5 range). The water-content bounds make
        # the result scale with monitored dwelling size instead of using a
        # one-size-fits-all mL trigger.
        daily_target = expected_daily_generation / 4.0
        lower = total_water * 0.06
        upper = total_water * 0.12
        ventilation_threshold = min(max(daily_target, lower), upper) if total_water > 0 else daily_target
        # On warm-season mornings/evenings, exploit cooler outside air by
        # lowering the trigger. This encourages early/late airing without
        # forcing ventilation during the hottest part of the day.
        avg_indoor_t = sum(float(r["temperature"]) * float(r["volume_m3"]) for r in valid) / max(sum(float(r["volume_m3"]) for r in valid), 1) if valid else 0.0
        opportunity = now.month in (5, 6, 7, 8, 9) and (now.hour < 9 or now.hour >= 19) and outdoor_t is not None and avg_indoor_t - outdoor_t >= 2.0
        if opportunity:
            ventilation_threshold *= 0.75
            threshold_reason = "adaptive_home_size_cool_window"
        else:
            threshold_reason = "adaptive_home_size"

    urgent_any = any(
        float(r.get("surface_rh", 0)) >= float(options.get("mould_critical_surface_rh", 90.0))
        or (r.get("co2_available", False) and float(r.get("co2", 0) or 0) >= float(options.get("co2_critical", 1400.0)))
        for r in valid
    )
    pollen_blocked = (
        bool(options.get("pollen_enabled", False))
        and bool(options.get("pollen_strict_veto", True))
        and pollen > float(options.get("pollen_max", 4.0))
        and not urgent_any
    )
    return pollen_blocked, threshold_reason, ventilation_threshold


def house_status_fallback(
    *,
    actionable_potential: Any,
    active: Any,
    bad: Any,
    close: Any,
    cooling: Any,
    options: Any,
    pollen_blocked: Any,
    sensor_recovery_grace: Any,
    valid: Any,
    ventilation_threshold: Any,
) -> str:
    """House status used when the intelligent recommendation carries no status.

    Priority (first match wins): sensor recovery, sensor error, close windows,
    ventilation running, critical indoor air in a ventilable room, summer cooling,
    pollen veto, potential above the house threshold, okay. Critical indoor air
    deliberately wins over cooling (hotfix 0.18.24).
    """
    urgent_actionable = any(
        r.get("ventilation_candidate", False)
        and (
            float(r.get("surface_rh", 0)) >= float(options.get("mould_critical_surface_rh", 90.0))
            or (r.get("co2_available", False) and float(r.get("co2", 0) or 0) >= float(options.get("co2_critical", 1400.0)))
        )
        for r in valid
    )
    if bad and sensor_recovery_grace:
        return "sensor_recovering"
    if bad:
        return "sensor_error"
    if close:
        return "close_windows"
    if active:
        return "ventilation_running"
    if urgent_actionable:
        return "ventilate"
    if cooling:
        return "cooling_recommended"
    if pollen_blocked and actionable_potential >= ventilation_threshold:
        return "pollen_warning"
    if actionable_potential >= ventilation_threshold:
        # The house-level "ventilate now" state is governed by the displayed
        # house threshold. High room RH remains visible in room/mould details,
        # but must not silently bypass the threshold shown to the user.
        return "ventilate"
    return "okay"

def floor_ventilation_decision(
    *,
    active: Any,
    cross: Any,
    forecast_confidence: Any,
    forecast_cost: Any,
    house_ventilation_mode: Any,
    intelligent_recommendation: Any,
    night_strategy: Any,
    options: Any,
    valid: Any,
) -> Any:
    """Phase 3: decide whether rooms of one floor should be aired together."""
    active_by_floor: dict[str, list[dict[str, Any]]] = {}
    valid_by_floor: dict[str, list[dict[str, Any]]] = {}
    for _r in valid:
        valid_by_floor.setdefault(str(_r.get("floor") or "Unzugeordnet"), []).append(_r)
    for _r in active:
        active_by_floor.setdefault(str(_r.get("floor") or "Unzugeordnet"), []).append(_r)
    floor_name, floor_active = max(active_by_floor.items(), key=lambda item: len(item[1]), default=("", []))
    floor_display_name = {"ground_floor": "Erdgeschoss", "upper_floor": "Obergeschoss", "basement": "Kellergeschoss", "base_floor": "Kellergeschoss", "attic": "Dachgeschoss", "other": "Sonstiger Bereich"}.get(str(floor_name), str(floor_name or "Stockwerk"))
    floor_total = len(valid_by_floor.get(floor_name, [])) if floor_name else 0
    floor_active_ratio = (len(floor_active) / floor_total) if floor_total else 0.0
    # A changed real-world ventilation pattern must win over the previous
    # single-room recommendation. Two openings already count as floor mode
    # when they cover at least half of that floor; three active rooms always
    # establish a deliberate floor ventilation even on larger floors.
    floor_ventilation_mode = bool(
        not house_ventilation_mode and floor_total > 0
        and len(floor_active) >= 2
        and (len(floor_active) >= 3 or floor_active_ratio >= 0.5)
    )

    if house_ventilation_mode and active:
        intelligent_recommendation["presentation_scope"] = "house"
        intelligent_recommendation["presentation_active_rooms"] = len(active)
        intelligent_recommendation["presentation_total_rooms"] = len(valid)

        # Hotfix 0.20.2.5: house ventilation is a real aggregate decision,
        # not a presentation wrapper around room-by-room close commands.
        # The next 5-minute benefit and thermal cost are aggregated across
        # every actively ventilated room. Individual close requests are
        # suppressed until the common house endpoint is reached.
        # Signed NET five-minute effect. Positive means the house loses
        # moisture, negative means it gains moisture. Previously negative
        # rooms were discarded here, while the card displayed their signed
        # contribution; that produced contradictions such as −9 ml in the
        # tile but "14 ml Entfeuchtung" in the explanation.
        house_next5_removed = sum(float(r.get("forecast_5_min_net_moisture_change_ml", r.get("forecast_5_min_moisture_effect_ml", 0.0)) or 0.0) for r in active)
        house_next5_temp_loss = sum(
            max(-float(r.get("forecast_5_min_temperature_change_c", 0.0)), 0.0) * float(r.get("volume_m3", 0.0))
            for r in active
        ) / max(sum(float(r.get("volume_m3", 0.0)) for r in active), 1.0)
        house_min_return = float(options.get("min_return_next_5_min_ml", 25.0)) * max(len(active) ** 0.5, 1.0) * _mean_volume_factor(active)
        house_efficiency = 999.0 if house_next5_temp_loss <= 0.05 else house_next5_removed / (house_next5_temp_loss * 10.0)
        house_thermal_bad = (
            str(options.get("operating_profile", "comfort")) != "summer_cooling"
            and house_next5_temp_loss >= float(options.get("max_temp_loss_next_5_min_c", 0.6))
            and house_efficiency < float(options.get("min_efficiency_ml_per_01c", 8.0))
        )
        house_low_return = house_next5_removed < house_min_return
        house_close_gate_ready = aggregate_close_gate_ready(active)
        house_should_close = aggregate_close_allowed(
            active, low_return=house_low_return, thermal_bad=house_thermal_bad,
            min_duration_min=float(options.get("min_duration_min", 3.0)),
        )
        active_room_keys = [str(r.get("key")) for r in active]

        intelligent_recommendation["house_next_5_min_moisture_effect_ml"] = round(house_next5_removed)
        intelligent_recommendation["house_next_5_min_temperature_loss_c"] = round(house_next5_temp_loss, 2)
        intelligent_recommendation["house_decision_threshold_ml"] = round(house_min_return)
        intelligent_recommendation["room_keys"] = active_room_keys
        active_room_names = [str(r.get("name") or r.get("key")) for r in active]
        intelligent_recommendation["selected_rooms"] = active_room_names
        if house_should_close:
            intelligent_recommendation["kind"] = "close"
            intelligent_recommendation["status"] = "close_windows"
            intelligent_recommendation["title"] = "Der sinnvolle Lüftungspunkt ist erreicht"
            intelligent_recommendation["instruction"] = "Hauslüftung beenden"
            intelligent_recommendation["summary"] = "Der zusätzliche Gesamtnutzen der Hauslüftung ist gegenüber Feuchteziel und Temperaturverlust nicht mehr ausreichend."
            intelligent_recommendation["reasons"] = [
                f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {round(house_next5_removed)} ml Feuchteabbau" if house_next5_removed >= 0 else f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {abs(round(house_next5_removed))} ml Feuchtezunahme",
                f"Gemeinsamer Schwellwert für diese Hauslüftung: etwa {round(house_min_return)} ml in 5 Minuten",
                f"Mittlere prognostizierte Abkühlung der aktiven Räume: {house_next5_temp_loss:.1f} °C",
            ]
        else:
            intelligent_recommendation["kind"] = "continue"
            intelligent_recommendation["status"] = "ventilation_running"
            intelligent_recommendation["title"] = "Hauslüftung läuft"
            intelligent_recommendation["instruction"] = "Hausweit weiterlüften"
            if house_close_gate_ready:
                intelligent_recommendation["summary"] = "Die Hauslüftung bringt insgesamt noch ausreichend Nutzen. FreshAirIQ bewertet die aktiven Räume gemeinsam und gibt währenddessen keine einzelnen Schließhinweise aus."
                gate_reason = None
            else:
                intelligent_recommendation["summary"] = "Die Schließentscheidung bleibt gesperrt, bis alle aktiven Räume zwei neue Feuchtemeldungen geliefert haben oder die 15-Minuten-Modellfreigabe greift."
                ready_count = sum(bool(r.get("close_decision_ready", False)) for r in active)
                gate_reason = f"Schließfreigabe noch nicht vollständig: {ready_count}/{len(active)} aktive Räume freigegeben"
                if intelligent_recommendation.get("duration_min") in (0, 0.0):
                    intelligent_recommendation["duration_min"] = None
            intelligent_recommendation["reasons"] = [
                *([gate_reason] if gate_reason else []),
                f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {round(house_next5_removed)} ml Feuchteabbau" if house_next5_removed >= 0 else f"Hausweiter Nettoeffekt der nächsten 5 Minuten: {abs(round(house_next5_removed))} ml Feuchtezunahme",
                f"Gemeinsamer Schwellwert für diese Hauslüftung: etwa {round(house_min_return)} ml in 5 Minuten",
                f"Mittlere prognostizierte Abkühlung der aktiven Räume: {house_next5_temp_loss:.1f} °C",
            ]

        # The frontend deliberately prefers decision_brain over the raw
        # recommendation fields. Replace the previously room-specific brain
        # with the aggregate house decision, otherwise stale room chips and
        # room wording would remain visible despite the correct house logic.
        intelligent_recommendation["decision_brain"] = {
            "version": "v1-house",
            "decision_label": "HAUSLÜFTUNG",
            "headline": intelligent_recommendation["title"],
            "action_line": intelligent_recommendation["instruction"],
            "summary": intelligent_recommendation["summary"],
            "why": list(intelligent_recommendation.get("reasons") or []),
            "impact": {
                "moisture_ml": round(house_next5_removed),
                "temperature_c": round(-house_next5_temp_loss, 2),
                "cost": round(float(forecast_cost), 2),
                "duration_min": intelligent_recommendation.get("duration_min"),
                "confidence": round(float(forecast_confidence)),
            },
            "comparison": {},
            "alternative": None,
            "selected_rooms": active_room_names,
            "presentation_scope": "house",
            "presentation_floor": None,
            "short_term_options": 0,
            "long_term_options": 0,
            "cross_ventilation": bool(cross),
            "night_strategy": night_strategy if isinstance(night_strategy, dict) else {},
            "night_strategy_primary": False,
        }
    elif floor_ventilation_mode:
        floor_next5_removed = sum(float(r.get("forecast_5_min_net_moisture_change_ml", r.get("forecast_5_min_moisture_effect_ml", 0.0)) or 0.0) for r in floor_active)
        floor_temp_loss = sum(max(-float(r.get("forecast_5_min_temperature_change_c", 0.0)), 0.0) * float(r.get("volume_m3", 0.0)) for r in floor_active) / max(sum(float(r.get("volume_m3", 0.0)) for r in floor_active), 1.0)
        floor_threshold = float(options.get("min_return_next_5_min_ml", 25.0)) * max(len(floor_active) ** 0.5, 1.0) * _mean_volume_factor(floor_active)
        floor_efficiency = 999.0 if floor_temp_loss <= 0.05 else floor_next5_removed / (floor_temp_loss * 10.0)
        floor_thermal_bad = (str(options.get("operating_profile", "comfort")) != "summer_cooling" and floor_temp_loss >= float(options.get("max_temp_loss_next_5_min_c", 0.6)) and floor_efficiency < float(options.get("min_efficiency_ml_per_01c", 8.0)))
        floor_low_return = floor_next5_removed < floor_threshold
        floor_close_gate_ready = aggregate_close_gate_ready(floor_active)
        floor_should_close = aggregate_close_allowed(
            floor_active, low_return=floor_low_return, thermal_bad=floor_thermal_bad,
            min_duration_min=float(options.get("min_duration_min", 3.0)),
        )
        intelligent_recommendation["presentation_scope"] = "floor"
        intelligent_recommendation["presentation_floor"] = floor_display_name
        intelligent_recommendation["room_keys"] = [str(r.get("key")) for r in floor_active]
        floor_room_names = [str(r.get("name") or r.get("key")) for r in floor_active]
        intelligent_recommendation["selected_rooms"] = floor_room_names
        intelligent_recommendation["floor_next_5_min_moisture_effect_ml"] = round(floor_next5_removed)
        if floor_should_close:
            intelligent_recommendation.update({
                "kind": "close", "status": "close_windows",
                "title": "Etagenlüftung hat ihr sinnvolles Ziel erreicht",
                "instruction": f"{floor_display_name} schließen",
                "summary": "FreshAirIQ hat die Situation nach den zusätzlich geöffneten Fenstern neu bewertet. Die Räume werden jetzt als gemeinsame Etagenlüftung beurteilt; der zusätzliche Gesamtnutzen ist nicht mehr ausreichend.",
                "reasons": [f"{len(floor_active)} aktive Lüftungsräume auf dieser Etage werden gemeinsam bewertet", f"Nettoeffekt der nächsten 5 Minuten: {round(floor_next5_removed)} ml", f"Gemeinsamer Schwellwert: etwa {round(floor_threshold)} ml in 5 Minuten"],
            })
        else:
            floor_ready_count = sum(bool(r.get("close_decision_ready", False)) for r in floor_active)
            floor_gate_reason = None if floor_close_gate_ready else f"Schließfreigabe noch nicht vollständig: {floor_ready_count}/{len(floor_active)} aktive Räume freigegeben"
            intelligent_recommendation.update({
                "kind": "continue", "status": "ventilation_running",
                "title": "Situation neu eingeschätzt: Etagenlüftung läuft",
                "instruction": f"{floor_display_name} gemeinsam weiterlüften",
                "summary": "Durch die zusätzlich geöffneten Fenster hat sich die Lüftungssituation geändert. FreshAirIQ bewertet jetzt die Wirkung der gesamten Etage statt an der früheren Einzelraum-Empfehlung festzuhalten." if floor_close_gate_ready else "Die Schließentscheidung bleibt gesperrt, bis alle aktiven Räume dieser Etage zwei neue Feuchtemeldungen geliefert haben oder die 15-Minuten-Modellfreigabe greift.",
                "reasons": [*([floor_gate_reason] if floor_gate_reason else []), f"{len(floor_active)} aktive Lüftungsräume auf derselben Etage erkannt", f"Gemeinsamer Nettoeffekt der nächsten 5 Minuten: {round(floor_next5_removed)} ml", f"Gemeinsamer Schwellwert: etwa {round(floor_threshold)} ml in 5 Minuten"],
            })
            if not floor_close_gate_ready and intelligent_recommendation.get("duration_min") in (0, 0.0):
                intelligent_recommendation["duration_min"] = None
        intelligent_recommendation["decision_brain"] = {
            "version": "v1-floor", "decision_label": "ETAGENLÜFTUNG",
            "headline": intelligent_recommendation["title"], "action_line": intelligent_recommendation["instruction"],
            "summary": intelligent_recommendation["summary"], "why": list(intelligent_recommendation.get("reasons") or []),
            "impact": {"moisture_ml": round(floor_next5_removed), "temperature_c": round(-floor_temp_loss, 2), "cost": round(float(forecast_cost), 2), "duration_min": intelligent_recommendation.get("duration_min"), "confidence": round(float(forecast_confidence))},
            "comparison": {}, "alternative": None, "selected_rooms": floor_room_names, "presentation_scope": "floor", "presentation_floor": floor_display_name, "short_term_options": 0, "long_term_options": 0, "cross_ventilation": bool(cross), "night_strategy": night_strategy if isinstance(night_strategy, dict) else {}, "night_strategy_primary": False,
        }
    else:
        intelligent_recommendation["presentation_scope"] = "rooms"
    return floor_display_name, floor_ventilation_mode

def build_night_strategy(
    *,
    avg_indoor_ah: Any,
    first_rain_dt: Any,
    max_night_temp_loss_c: Any,
    minutes_until_rain: Any,
    night_ah_delta: Any,
    night_avg_ah: Any,
    night_avg_temp: Any,
    night_confidence: Any,
    night_energy_cost: Any,
    night_energy_kwh: Any,
    night_forecast: Any,
    night_forecast_closed: Any,
    night_forecast_with_selected: Any,
    night_hours: Any,
    night_max_rh: Any,
    night_min_temp: Any,
    night_rain_expected: Any,
    night_rain_mm: Any,
    night_rain_prob: Any,
    night_strategy_relevant: Any,
    night_temperature_change_c: Any,
    night_weather_available: Any,
    open_rooms: Any,
    pre_vent_effect: Any,
    pre_vent_source_ah: Any,
    prebed_minutes: Any,
    rain_start_label: Any,
    selected_night: Any,
    selected_night_names: Any,
    selected_weather_effect: Any,
    thermal_ok: Any,
) -> Any:
    """Phase 3: assemble the night strategy (close / pre-ventilate / open selected rooms) from the night forecast."""
    night_forecast_after_prevent = round(night_forecast_closed + pre_vent_effect) if pre_vent_effect < -1.0 else None

    night_strategy = {
        "active": night_strategy_relevant,
        "weather_available": night_weather_available,
        "action": "monitor",
        "label": "NACHTSTRATEGIE",
        "headline": "FreshAirIQ beobachtet die Nachtentwicklung",
        "instruction": "Fensterzustand vor der Nacht erneut bewerten",
        "summary": "Die Wetter- und Feuchteprognose reicht noch nicht für eine belastbare Fensterstrategie.",
        "reasons": [],
        "confidence": min(night_confidence, 65 if not night_weather_available else 95),
        "rain_expected": night_rain_expected,
        "rain_probability": round(night_rain_prob),
        "rain_mm": round(night_rain_mm, 1),
        "rain_start": first_rain_dt.isoformat() if isinstance(first_rain_dt, datetime) else None,
        "rain_start_label": rain_start_label,
        "minutes_until_rain": round(minutes_until_rain) if minutes_until_rain is not None else None,
        "outside_ah_g_m3": round(night_avg_ah, 2) if night_avg_ah is not None else None,
        "inside_ah_g_m3": round(avg_indoor_ah, 2),
        "outside_minus_inside_ah_g_m3": round(night_ah_delta, 2) if night_ah_delta is not None else None,
        "min_temperature_c": round(night_min_temp, 1) if night_min_temp is not None else None,
        "average_temperature_c": round(night_avg_temp, 1) if night_avg_temp is not None else None,
        "projected_room_temperature_change_c": round(night_temperature_change_c, 1) if night_temperature_change_c is not None else None,
        "max_acceptable_room_temperature_loss_c": round(max_night_temp_loss_c, 1),
        "projected_reheat_energy_kwh": round(night_energy_kwh, 2),
        "projected_reheat_cost": round(night_energy_cost, 2),
        "max_humidity": round(night_max_rh) if night_max_rh is not None else None,
        "open_rooms": [str(x) for x in open_rooms if x],
        "selected_rooms": selected_night_names,
        "forecast_ml": night_forecast,
        "forecast_current_state_ml": night_forecast,
        "forecast_closed_windows_ml": night_forecast_closed,
        "forecast_without_action_ml": night_forecast_closed,
        "forecast_with_strategy_ml": None,
        "strategy_moisture_effect_ml": None,
        "hours": round(night_hours, 1),
    }
    if night_strategy_relevant and night_weather_available and night_ah_delta is not None:
        if night_rain_expected and night_ah_delta > -0.6:
            night_strategy.update({
                "action": "close",
                "label": "NACHT · FENSTER SCHLIESSEN",
                "headline": "Heute Nacht Fenster geschlossen halten",
                "instruction": "Alle geöffneten Fenster vor der Nacht schließen" if open_rooms else "Fenster über Nacht geschlossen lassen",
                "summary": "Die Nachtprognose erwartet Niederschlag und keine ausreichend trockenere Außenluft. Offene Fenster würden den Feuchteschutz daher nicht sinnvoll unterstützen.",
                "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                "forecast_with_strategy_ml": night_forecast_closed,
                "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                "reasons": [
                    (f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else (f"Niederschlagsrisiko bis {round(night_rain_prob)} %" if night_rain_prob else "Niederschlag wird in der Nacht erwartet")),
                    f"Nachtluft liegt im Mittel bei {night_avg_ah:.1f} g/m³ absoluter Feuchte",
                    f"Mit geschlossenen Fenstern werden bis zum Nachtende etwa {night_forecast_closed:+.0f} ml erwartet",
                ],
            })
        elif night_ah_delta <= -0.6 and night_rain_expected:
            # A rain forecast only justifies pre-ventilation when there is
            # a real dry window left before precipitation starts. Otherwise
            # closing is the only actionable, safe statement.
            dry_before_rain = pre_vent_source_ah is not None and pre_vent_source_ah <= avg_indoor_ah - 0.6
            enough_time = minutes_until_rain is not None and minutes_until_rain >= prebed_minutes + 5
            if selected_night and dry_before_rain and enough_time:
                room_text = " + ".join(selected_night_names)
                deadline = f" bis spätestens {rain_start_label} Uhr" if rain_start_label else " vor der Regenphase"
                night_strategy.update({
                    "action": "pre_ventilate",
                    "label": "NACHT · VORHER LÜFTEN",
                    "headline": "Trockene Luft vor dem Regen gezielt nutzen",
                    "instruction": f"{room_text}{deadline} etwa {prebed_minutes} Minuten stoßlüften und danach schließen",
                    "summary": "Vor Beginn des Niederschlags bleibt ein ausreichend trockenes Lüftungsfenster. Danach empfiehlt FreshAirIQ wegen des Regens keine unbeaufsichtigte Daueröffnung.",
                    "forecast_without_action_ml": night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_after_prevent,
                    "strategy_moisture_effect_ml": round(pre_vent_effect),
                    "reasons": [
                        f"Vor der Regenphase ist die Außenluft etwa {abs((pre_vent_source_ah or avg_indoor_ah) - avg_indoor_ah):.1f} g/m³ trockener als die Raumluft",
                        f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else f"Niederschlagsrisiko bis {round(night_rain_prob)} %",
                        f"Für das Stoßlüften sind noch etwa {round(minutes_until_rain)} Minuten Zeit" if minutes_until_rain is not None else "Zeitfenster vor dem Regen ist ausreichend",
                    ],
                })
            else:
                night_strategy.update({
                    "action": "close",
                    "label": "NACHT · FENSTER SCHLIESSEN",
                    "headline": "Regenfenster ist für Vorlüften zu knapp",
                    "instruction": "Fenster über Nacht geschlossen lassen",
                    "summary": "Die Nachtluft wäre zeitweise trocken genug, vor dem prognostizierten Regen bleibt aber kein ausreichend belastbares Lüftungsfenster für eine sichere Vorlüftung.",
                    "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                    "forecast_with_strategy_ml": night_forecast_closed,
                    "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                    "reasons": [
                        f"Regenphase beginnt voraussichtlich gegen {rain_start_label} Uhr" if rain_start_label else f"Niederschlagsrisiko bis {round(night_rain_prob)} %",
                        f"Benötigtes Stoßlüftungsfenster etwa {prebed_minutes} Minuten plus Sicherheitsreserve",
                        "FreshAirIQ empfiehlt keine Nachtöffnung ohne ausreichendes trockenes Zeitfenster",
                    ],
                })
        elif night_ah_delta <= -0.6 and thermal_ok and selected_night:
            room_text = " + ".join(selected_night_names)
            night_strategy.update({
                "action": "open_selected",
                "label": "NACHT · KONTROLLIERT LÜFTEN",
                "headline": "Die Nacht eignet sich für kontrollierte Nachtlüftung",
                "instruction": f"{room_text} über Nacht nur teilweise geöffnet lassen",
                "summary": "Die prognostizierte Nachtluft bleibt deutlich trockener und das thermische Modell erwartet für genau diese ausgewählten Räume nur eine begrenzte Abkühlung.",
                "forecast_without_action_ml": night_forecast_closed,
                "forecast_with_strategy_ml": night_forecast_with_selected,
                "strategy_moisture_effect_ml": round(selected_weather_effect),
                "reasons": [
                    f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                    f"Ausgewählt: {room_text}; erwartete mittlere Abkühlung etwa {abs(night_temperature_change_c or 0):.1f} °C (Grenze {max_night_temp_loss_c:.1f} °C)",
                    f"Geschätzter Wiederaufheizbedarf etwa {night_energy_kwh:.2f} kWh / {night_energy_cost:.2f} €",
                    f"Fenster zu: {night_forecast_closed:+.0f} ml · mit Strategie: {float(night_forecast_with_selected or 0):+.0f} ml",
                ],
            })
        elif night_ah_delta <= -0.6 and selected_night and not thermal_ok:
            room_text = " + ".join(selected_night_names)
            night_strategy.update({
                "action": "pre_ventilate",
                "label": "NACHT · VORHER LÜFTEN",
                "headline": "Trockene Nachtluft nutzen, aber nicht dauerhaft",
                "instruction": f"Vor dem Schlafengehen {room_text} etwa {prebed_minutes} Minuten stoßlüften und danach schließen",
                "summary": "Die Nachtluft wäre für den Feuchteabbau geeignet, eine dauerhafte Öffnung würde die ausgewählten Räume laut thermischem Modell jedoch zu stark abkühlen.",
                "forecast_without_action_ml": night_forecast_closed,
                "forecast_with_strategy_ml": night_forecast_after_prevent,
                "strategy_moisture_effect_ml": round(pre_vent_effect) if pre_vent_effect < -1 else None,
                "reasons": [
                    f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                    f"Dauerlüftung in {room_text} würde dort im Mittel etwa {abs(night_temperature_change_c or 0):.1f} °C Abkühlung verursachen",
                    f"FreshAirIQ akzeptiert höchstens etwa {max_night_temp_loss_c:.1f} °C prognostizierten Verlust",
                    f"Tiefste Außentemperatur etwa {night_min_temp:.1f} °C" if night_min_temp is not None else "Die Temperaturprognose wird weiter bewertet",
                ],
            })
        elif night_ah_delta <= -0.6 and not selected_night:
            night_strategy.update({
                "action": "closed_monitor",
                "label": "NACHT · BEOBACHTEN",
                "headline": "Trockene Nachtluft erkannt, aber kein Fenster sicher auswählbar",
                "instruction": "Fenster zunächst geschlossen lassen",
                "summary": "Die Außenluft wäre günstig, FreshAirIQ hat jedoch keinen berechenbaren Raum mit konfiguriertem Lüftungskontakt gefunden. Deshalb wird keine pauschale Nachtöffnung empfohlen.",
                "reasons": [
                    f"Nachtluft ist im Mittel etwa {abs(night_ah_delta):.1f} g/m³ trockener als die Raumluft",
                    "Für kontrollierte Nachtlüftung muss mindestens ein geeigneter Raum mit Fenster-/Türkontakt eindeutig auswählbar sein",
                ],
            })
        elif night_ah_delta >= 0.4:
            night_strategy.update({
                "action": "close",
                "label": "NACHT · FENSTER SCHLIESSEN",
                "headline": "Feuchte Nachtluft besser draußen lassen",
                "instruction": "Fenster über Nacht geschlossen lassen",
                "summary": "Die prognostizierte Außenluft ist feuchter als die aktuelle Raumluft. Dauerhaft offene Fenster würden voraussichtlich zusätzliche Feuchtigkeit eintragen.",
                "forecast_without_action_ml": night_forecast if open_rooms else night_forecast_closed,
                "forecast_with_strategy_ml": night_forecast_closed,
                "strategy_moisture_effect_ml": night_forecast_closed - (night_forecast if open_rooms else night_forecast_closed),
                "reasons": [
                    f"Nachtluft ist im Mittel etwa {night_ah_delta:.1f} g/m³ feuchter als die Raumluft",
                    f"Maximale prognostizierte relative Außenfeuchte etwa {round(night_max_rh or 0)} %",
                    f"Mit geschlossenen Fenstern werden bis zum Nachtende etwa {night_forecast_closed:+.0f} ml erwartet",
                ],
            })
        else:
            night_strategy.update({
                "action": "closed_monitor",
                "label": "NACHT · BEOBACHTEN",
                "headline": "Für die Nacht ist kein Dauerlüften nötig",
                "instruction": "Fenster zunächst geschlossen lassen",
                "summary": "Außenfeuchte und Temperatur ergeben aktuell keinen klaren Vorteil für dauerhaft geöffnete Fenster. FreshAirIQ bewertet die Nacht weiter neu.",
                "forecast_without_action_ml": night_forecast_closed,
                "forecast_with_strategy_ml": night_forecast_closed,
                "strategy_moisture_effect_ml": 0,
                "reasons": [
                    f"Differenz Außen-/Innenfeuchte nachts nur {night_ah_delta:+.1f} g/m³",
                    f"Tiefste prognostizierte Außentemperatur etwa {night_min_temp:.1f} °C" if night_min_temp is not None else "Temperaturprognose wird weiter beobachtet",
                ],
            })
    return night_strategy
