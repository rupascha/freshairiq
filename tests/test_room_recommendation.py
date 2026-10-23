"""Room-specific recommendation (room_recommendation._recommendation): every branch."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.freshairiq.model import SUMMER_WARMING_CLOSE_REASON
from custom_components.freshairiq.room_recommendation import _recommendation

WIND = {"pollen": 0.0, "co2": None, "airflow": 1.0, "wind_bearing": None, "wind_speed": None}


def _result(**overrides):
    base = {
        "data_quality": "ok", "humidity": 50.0, "surface_rh": 60.0, "delta_g_m3": 0.0,
        "active": False, "close_recommended": False, "ventilation_candidate": False,
        "cooling_candidate": False, "potential_ml": 0, "moisture_effect_next_5_min_ml": 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _rec(result, options=None, **kwargs):
    return _recommendation(result, options or {}, **{**WIND, **kwargs})


def test_invalid_measurements_ask_for_a_sensor_check():
    action, reason, reasons = _rec(_result(data_quality="stale"))
    assert action == "Check sensor" and reason == "Messwerte fehlen oder sind unplausibel" and len(reasons) == 1


def test_active_moisture_source_keeps_ventilating_and_wind_support_is_explained():
    result = _result(
        humidity=70.0, surface_rh=85.0, active=True, delta_g_m3=2.0,
        moisture_source_active=True, moisture_source_label="Dusche",
        moisture_source_confidence=80, moisture_source_rate_ml_min=2.0,
    )
    action, reason, reasons = _rec(result, {"operating_profile": "dehumidify"}, co2=1500.0, airflow=1.2, wind_bearing=180.0)
    assert action == "Continue ventilating"
    assert "zu hoch" in reasons[0] and "Schimmelrisiko" in reasons[1] and "kritisch" in reasons[2]
    assert "Dusche wahrscheinlich aktiv (80 % Sicherheit)" in reason and "120 ml/h" in reason
    assert reasons[-1] == "Windrichtung unterstützt den Luftwechsel"


def test_close_texts_cover_fallback_weather_risk_summer_and_target():
    risk = _result(humidity=63.0, active=True, close_recommended=True,
                   close_decision_model_fallback=True, future_moisture_risk_15=True)
    action, _reason, reasons = _rec(risk, co2=1100.0)
    assert action == "Close" and "Lüftungsstartwert" in reasons[0] and "Warnschwelle" in reasons[1]
    assert "Wetterprognose" in reasons[-1]
    model = _result(active=True, close_recommended=True, close_decision_model_fallback=True)
    assert "ersatzweise" in _rec(model)[2][-1]
    summer = _result(active=True, close_recommended=True, reason=SUMMER_WARMING_CLOSE_REASON)
    assert _rec(summer)[2][-1] == "Die Außenluft ist nicht mehr kühler als der Raum; Schließen hält die Kühle im Raum"
    target = _result(active=True, close_recommended=True)
    assert _rec(target)[2][-1] == "Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering"


def test_continue_texts_and_weak_or_braking_wind():
    waiting = _result(active=True, close_decision_ready=False, fresh_measurements=1)
    action, _reason, reasons = _rec(waiting, airflow=0.8, wind_bearing=0.0)
    assert action == "Continue ventilating" and reasons[0] == "Schließentscheidung wartet auf neue Klimamessungen (1/2)"
    assert reasons[-1] == "Windrichtung bremst den Luftwechsel"
    fallback = _result(active=True, close_decision_model_fallback=True)
    assert "Modellbewertung" in _rec(fallback)[2][0]
    cooling = _result(active=True, reason="Cooling remains useful because ...")
    reasons = _rec(cooling, wind_bearing=90.0, wind_speed=3.0)[2]
    assert reasons[0].startswith("Kühlen wirkt weiter") and reasons[-1] == "Wind hat aktuell nur geringen Einfluss"
    plain = _result(active=True, moisture_effect_next_5_min_ml=42.4)
    assert _rec(plain, {"wind_orientation_enabled": False}, wind_bearing=90.0)[2] == [
        "Kurzfristiger Schließcheck (5 min): voraussichtlich 42 ml Feuchteabbau"
    ]
    assert _rec(_result(active=True), wind_bearing=90.0)[2][-1] == "Kurzfristiger Schließcheck (5 min): voraussichtlich 0 ml Feuchteabbau"


def test_outdoor_air_veto_names_pollen_and_fine_dust():
    options = {"pollen_enabled": True, "pollen_max": 3}
    action, _reason, reasons = _rec(_result(ventilation_candidate=True), options, pollen=4.5, outdoor_pm25=80.0)
    assert action == "Do not ventilate"
    assert reasons[0] == "Pollenindex 4.5 liegt über dem Grenzwert 3.0"
    assert reasons[1].startswith("Feinstaub draußen (PM2.5) 80")
    only_dust = _rec(_result(cooling_candidate=True), {}, outdoor_pm25=80.0)
    assert only_dust[0] == "Do not ventilate" and len(only_dust[2]) == 1


def test_ventilation_candidate_with_latched_advice_and_cooling_candidate():
    high = _result(humidity=69.0, delta_g_m3=1.0, ventilation_candidate=True, potential_ml=210.4)
    action, _reason, reasons = _rec(high, ventilation_latched=True)
    assert action == "Ventilate"
    assert "mindestens 1.5 g/m³ nötig" in reasons[1] and reasons[2] == "Aktuell sind etwa 210 ml Feuchtigkeit entfernbar"
    assert reasons[3].startswith("Empfehlung bleibt trotz leichter Schwankung bestehen")
    start = _result(humidity=63.0, delta_g_m3=3.0, ventilation_candidate=True)
    assert len(_rec(start, ventilation_latched=True)[2]) == 3
    assert _rec(_result(cooling_candidate=True))[0] == "Ventilate for cooling"


def test_room_problem_with_unsuitable_air_and_idle_states():
    wetter = _rec(_result(humidity=70.0, delta_g_m3=0.0))
    assert wetter[0] == "Do not ventilate" and "gleich feucht oder feuchter" in wetter[1]
    weak = _rec(_result(humidity=63.0, surface_rh=81.0, delta_g_m3=0.5))
    assert weak[0] == "Wait" and "benötigt werden etwa 2.5 g/m³" in weak[1]
    assert _rec(_result(delta_g_m3=-1.0))[0] == "Do not ventilate"
    assert _rec(_result(potential_ml=5))[0] == "Wait"
    assert _rec(_result()) == ("Okay", "Kein relevanter Lüftungsbedarf", ["Kein relevanter Lüftungsbedarf"])
