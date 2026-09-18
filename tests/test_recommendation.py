from custom_components.freshairiq.recommendation import build_recommendation


def base_options():
    return {
        "start_rh": 62.0,
        "high_rh": 68.0,
        "mould_warn_surface_rh": 80.0,
        "mould_critical_surface_rh": 90.0,
        "co2_warn": 1000.0,
        "co2_critical": 1400.0,
        "cross_ventilation_pairs": "living+wc",
    }


def room(key, name, **kw):
    d = {
        "key": key,
        "name": name,
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": False,
        "action": "Okay",
        "humidity": 55,
        "surface_rh": 60,
        "mould_level": "Low",
        "co2": 500,
        "potential_ml": 0,
        "delta_g_m3": 0,
        "airflow_factor": 1.0,
        "temp_next_5_min_c": -0.2,
        "next_5_min_cost": 0.01,
        "moisture_effect_next_5_min_ml": 0,
        "forecast_horizon_min": 15,
        "forecast_moisture_effect_ml": 0,
        "forecast_temperature_change_c": -0.4,
        "forecast_cost": 0.02,
        "humidity_trend_pct_h": 0,
        "humidity_high_duration_min": 0,
    }
    d.update(kw)
    return d


def test_targeted_high_humidity_can_trigger_below_house_threshold():
    rooms = {
        "bed": room("bed", "Schlafzimmer", action="Ventilate", humidity=70, potential_ml=130, delta_g_m3=2.4),
        "living": room("living", "Wohnzimmer"),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=130, recommended_duration_min=8)
    assert out["kind"] == "ventilate"
    assert out["title"] == "Jetzt gezielt lüften"
    assert out["room_names"] == ["Schlafzimmer"]
    assert any("Schlafzimmer" in x and "70" in x for x in out["reasons"])


def test_high_humidity_with_wetter_outside_waits_and_explains():
    rooms = {
        "store": room("store", "Lagerraum", action="Do not ventilate", humidity=75, potential_ml=0, delta_g_m3=-0.8),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=0, recommended_duration_min=8)
    assert out["kind"] == "wait"
    assert out["title"] == "Noch nicht lüften"
    assert "gleich feucht oder feuchter" in out["reasons"][0]


def test_cross_ventilation_pair_is_preferred_when_configured():
    rooms = {
        "living": room("living", "Wohnzimmer", action="Ventilate", humidity=69, potential_ml=250, delta_g_m3=3.0, airflow_factor=1.1),
        "wc": room("wc", "Gäste-WC", action="Ventilate", humidity=64, humidity_high_duration_min=45, potential_ml=180, delta_g_m3=2.7, airflow_factor=1.05),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=350, total_potential_ml=430, recommended_duration_min=7)
    assert out["title"] == "Jetzt querlüften"
    assert out["room_names"] == ["Wohnzimmer", "Gäste-WC"]
    assert any("Querlüftung" in x for x in out["reasons"])


def test_running_session_uses_configured_forecast_horizon_in_user_reason():
    rooms = {
        "bed": room(
            "bed", "Schlafzimmer", active=True, action="Continue ventilating",
            moisture_effect_next_5_min_ml=80, forecast_horizon_min=15,
            forecast_moisture_effect_ml=190, session_elapsed_min=4,
        ),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=0, recommended_duration_min=9)
    assert out["kind"] == "continue"
    assert any("Weitere 15 Minuten" in reason and "190 ml" in reason for reason in out["reasons"])
    assert not any("Weitere 5 Minuten" in reason for reason in out["reasons"])


def test_close_takes_precedence_over_continue():
    rooms = {
        "bed": room("bed", "Schlafzimmer", active=True, action="Close", close_recommended=True, moisture_effect_next_5_min_ml=5),
        "bath": room("bath", "Badezimmer", active=True, action="Continue ventilating", moisture_effect_next_5_min_ml=60),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=0, recommended_duration_min=9)
    assert out["kind"] == "close"
    assert out["room_names"] == ["Schlafzimmer"]


def test_night_strategy_becomes_primary_when_house_is_idle():
    from custom_components.freshairiq.decision_brain import build_unified_decision
    rec = {"kind": "okay", "title": "Okay", "instruction": "", "reasons": []}
    ns = {
        "active": True, "action": "close", "label": "NACHT · FENSTER SCHLIESSEN",
        "headline": "Heute Nacht Fenster geschlossen halten",
        "instruction": "Fenster über Nacht geschlossen lassen",
        "summary": "Feuchte Nachtluft.", "reasons": ["Regen erwartet"], "confidence": 82,
    }
    out = build_unified_decision(rec, {}, {}, night_strategy=ns)
    assert out["night_strategy_primary"] is True
    assert out["decision_brain"]["headline"] == "Heute Nacht Fenster geschlossen halten"
    assert out["decision_brain"]["decision_label"] == "NACHT · FENSTER SCHLIESSEN"
    assert "Regen erwartet" in out["decision_brain"]["why"]


def test_night_strategy_does_not_override_immediate_close():
    from custom_components.freshairiq.decision_brain import build_unified_decision
    rooms = {"bad": {"name": "Bad", "humidity": 70, "surface_rh": 75, "delta_g_m3": 2, "realistic_potential_ml": 80}}
    rec = {"kind": "close", "room_keys": ["bad"], "reasons": []}
    ns = {"active": True, "action": "open_selected", "headline": "Nachtlüften", "confidence": 90}
    out = build_unified_decision(rec, rooms, {}, night_strategy=ns)
    assert out.get("night_strategy_primary") is False
    assert out["decision_brain"]["decision_label"] == "JETZT SCHLIESSEN"
    assert "Bad schließen" in out["decision_brain"]["action_line"]


def test_close_reason_uses_configured_horizon_but_explains_short_term_gate():
    rooms = {
        "bed": room(
            "bed", "Schlafzimmer", active=True, action="Close", close_recommended=True,
            forecast_horizon_min=15, forecast_moisture_effect_ml=45,
            moisture_effect_next_5_min_ml=5,
        ),
    }
    out = build_recommendation(rooms, base_options(), threshold_ml=700, total_potential_ml=0, recommended_duration_min=9)
    assert out["kind"] == "close"
    text = " ".join(out["reasons"])
    assert "15 Minuten" in text
    assert "Schließschwelle" in text
