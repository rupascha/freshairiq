"""Room-specific recommendation text: trigger, suitability and action of one evaluated room."""
from __future__ import annotations

from typing import Any

from .model import SUMMER_WARMING_CLOSE_REASON, VENTILATION_HYSTERESIS_DELTA_G_M3, VENTILATION_HYSTERESIS_RH
from .outdoor_air import outdoor_pm25_blocked, pm25_reason


def _recommendation(result: Any, options: dict[str, Any], *, pollen: float, co2: float | None, airflow: float, wind_bearing: float | None, wind_speed: float | None, outdoor_pm25: float | None = None, ventilation_latched: bool = False) -> tuple[str, str, list[str]]:
    """Build a room-specific recommendation with an explicit trigger and suitability reason.

    The house threshold is intentionally *not* used here. A room can therefore
    require ventilation because of its own RH / surface-RH / CO2 even when the
    summed house potential is still below the house-wide threshold.
    """
    reasons: list[str] = []
    if result.data_quality != "ok":
        return "Check sensor", "Messwerte fehlen oder sind unplausibel", ["Messwerte fehlen oder sind unplausibel; Sensoren prüfen"]

    start_rh = float(options.get("start_rh", 62.0))
    high_rh = float(options.get("high_rh", 68.0))
    mould_warn = float(options.get("mould_warn_surface_rh", 80.0))
    mould_critical = float(options.get("mould_critical_surface_rh", 90.0))
    co2_warn = float(options.get("co2_warn", 1000.0))
    co2_critical = float(options.get("co2_critical", 1400.0))
    min_delta = float(options.get("min_delta", 2.5))
    min_delta_high = float(options.get("min_delta_high_rh", 1.5))
    if str(options.get("operating_profile", "comfort")) == "dehumidify":
        min_delta = max(0.1, min_delta * 0.85)
        min_delta_high = max(0.1, min_delta_high * 0.85)

    humidity_high = float(result.humidity or 0) >= high_rh
    humidity_start = float(result.humidity or 0) >= start_rh
    mould_high = float(result.surface_rh or 0) >= mould_warn
    co2_high = co2 is not None and co2 >= co2_warn
    co2_urgent = co2 is not None and co2 >= co2_critical
    urgent = float(result.surface_rh or 0) >= mould_critical or co2_urgent
    pollen_blocked = bool(options.get("pollen_enabled", False)) and bool(options.get("pollen_strict_veto", True)) and pollen > float(options.get("pollen_max", 4)) and not urgent
    pm25_blocked = outdoor_pm25_blocked(options, outdoor_pm25) and not urgent

    # State the room-specific trigger first. This text is shown verbatim in the
    # dashboard and notifications, so the user can immediately see *why* this
    # room needs attention.
    if humidity_high:
        reasons.append(f"Raumluftfeuchte {round(float(result.humidity or 0))} % ist zu hoch (Grenze {round(high_rh)} %)")
    elif humidity_start:
        reasons.append(f"Raumluftfeuchte {round(float(result.humidity or 0))} % liegt über dem Lüftungsstartwert {round(start_rh)} %")
    if mould_high:
        reasons.append(f"Oberflächenfeuchte {round(float(result.surface_rh or 0))} % erhöht das Schimmelrisiko")
    if co2_urgent:
        reasons.append(f"CO₂ {round(co2)} ppm ist kritisch (Grenze {round(co2_critical)} ppm)")
    elif co2_high:
        reasons.append(f"CO₂ {round(co2)} ppm liegt über der Warnschwelle {round(co2_warn)} ppm")

    source_active = bool(getattr(result, "moisture_source_active", False))
    source_label = str(getattr(result, "moisture_source_label", "Feuchtequelle") or "Feuchtequelle")
    source_conf = int(getattr(result, "moisture_source_confidence", 0) or 0)
    source_rate = float(getattr(result, "moisture_source_rate_ml_min", 0.0) or 0.0)
    if source_active:
        reasons.append(f"{source_label} wahrscheinlich aktiv ({source_conf} % Sicherheit); interne Feuchteproduktion etwa {source_rate * 60:.0f} ml/h")

    if result.active and source_active and float(result.delta_g_m3) > float(options.get("close_delta", 0.4)) and not (pollen_blocked or pm25_blocked):
        action = "Continue ventilating"
        reasons.append("Die Referenzluft ist weiterhin trockener; die steigende Raumfeuchte stammt trotz wirksamer Lüftung aus der aktiven Feuchtequelle")
    elif result.active and result.close_recommended:
        action = "Close"
        if bool(getattr(result, "close_decision_model_fallback", False)):
            if bool(getattr(result, "future_moisture_risk_15", False)):
                reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; Wetterprognose zeigt, dass der Trocknungsvorteil in den nächsten 15 Minuten voraussichtlich verloren geht")
            else:
                reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; FreshAirIQ entscheidet ersatzweise anhand des physikalischen und gelernten Lüftungsmodells")
        else:
            reasons.append(
                "Die Außenluft ist nicht mehr kühler als der Raum; Schließen hält die Kühle im Raum"
                if getattr(result, "reason", "") == SUMMER_WARMING_CLOSE_REASON
                else "Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering"
            )
    elif result.active:
        action = "Continue ventilating"
        if not bool(getattr(result, "close_decision_ready", True)):
            fresh = max(int(getattr(result, "fresh_measurements", 0) or 0), 0)
            reasons.append(f"Schließentscheidung wartet auf neue Klimamessungen ({fresh}/2)")
        elif bool(getattr(result, "close_decision_model_fallback", False)):
            reasons.append("Seit 15 Minuten fehlen zwei neue Klimamessungen; Modellbewertung sieht aktuell noch einen sinnvollen Lüftungsvorteil")
        elif str(getattr(result, "reason", "")).startswith("Cooling remains useful"):
            reasons.append("Kühlen wirkt weiter: die Außenluft ist deutlich kühler als der Raum")
        else:
            reasons.append(f"Kurzfristiger Schließcheck (5 min): voraussichtlich {max(round(result.moisture_effect_next_5_min_ml), 0)} ml Feuchteabbau")
    elif (pollen_blocked or pm25_blocked) and (result.ventilation_candidate or result.cooling_candidate):
        action = "Do not ventilate"
        if pollen_blocked:
            reasons.append(f"Pollenindex {pollen:.1f} liegt über dem Grenzwert {float(options.get('pollen_max',4)):.1f}")
        if pm25_blocked:
            reasons.append(pm25_reason(outdoor_pm25, options))
    elif result.ventilation_candidate:
        action = "Ventilate"
        required_delta = min_delta_high if humidity_high else min_delta
        reasons.append(f"Außen-/Referenzluft ist {float(result.delta_g_m3):.1f} g/m³ trockener (mindestens {required_delta:.1f} g/m³ nötig)")
        reasons.append(f"Aktuell sind etwa {max(round(result.potential_ml),0)} ml Feuchtigkeit entfernbar")
        delta_now = float(result.delta_g_m3)
        meets_fresh_start = (humidity_start and delta_now >= min_delta) or (humidity_high and delta_now >= min_delta_high)
        if ventilation_latched and not meets_fresh_start:
            # 0.26.4.7 (GitHub #15): explain why the advice stays although a
            # value dipped just below the start threshold.
            reasons.append(
                f"Empfehlung bleibt trotz leichter Schwankung bestehen: sie endet erst {VENTILATION_HYSTERESIS_RH:.0f} % "
                f"bzw. {VENTILATION_HYSTERESIS_DELTA_G_M3:.1f} g/m³ unter den Startwerten"
            )
    elif result.cooling_candidate:
        action = "Ventilate for cooling"
        reasons.append("Außenluft ist ausreichend kühler und der Feuchteeintrag bleibt vertretbar")
    elif humidity_high or mould_high or co2_high:
        # There is a genuine room problem, but the reference air is currently
        # unsuitable or not yet effective enough. Do not hide the trigger behind
        # a generic house-threshold message.
        if float(result.delta_g_m3) <= 0:
            action = "Do not ventilate"
            reasons.append("Lüften aktuell nicht sinnvoll: Außen-/Referenzluft ist gleich feucht oder feuchter")
        else:
            action = "Wait"
            required_delta = min_delta_high if humidity_high else min_delta
            reasons.append(f"Lüften noch nicht wirksam genug: Außen-/Referenzluft ist nur {float(result.delta_g_m3):.1f} g/m³ trockener; benötigt werden etwa {required_delta:.1f} g/m³")
    elif result.delta_g_m3 < -0.4:
        action = "Do not ventilate"
        reasons.append("Außen-/Referenzluft würde zusätzliche Feuchtigkeit eintragen")
    elif result.potential_ml > 0:
        action = "Wait"
        reasons.append("Etwas Entfeuchtungspotenzial vorhanden, aber noch kein raumspezifischer Lüftungsbedarf")
    else:
        action = "Okay"
        reasons.append("Kein relevanter Lüftungsbedarf")

    if bool(options.get("wind_orientation_enabled", True)) and wind_bearing is not None and action in {"Ventilate", "Continue ventilating", "Ventilate for cooling"}:
        if airflow >= 1.12:
            reasons.append("Windrichtung unterstützt den Luftwechsel")
        elif airflow <= .88:
            reasons.append("Windrichtung bremst den Luftwechsel")
        elif wind_speed is not None:
            reasons.append("Wind hat aktuell nur geringen Einfluss")
    return action, "; ".join(reasons), reasons
