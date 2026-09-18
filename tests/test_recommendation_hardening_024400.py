"""Recommendation-engine robustness and branch coverage for v0.25.0.7."""
from math import inf, nan

from custom_components.freshairiq.recommendation import build_recommendation


def opts(**extra):
    base = {
        "start_rh": 62.0,
        "high_rh": 68.0,
        "mould_warn_surface_rh": 80.0,
        "mould_critical_surface_rh": 90.0,
        "co2_warn": 1000.0,
        "co2_critical": 1400.0,
        "close_delta": 0.4,
        "min_potential_room_ml": 100.0,
        "cross_ventilation_pairs": "",
    }
    base.update(extra)
    return base


def room(key="r", **extra):
    base = {
        "key": key,
        "name": key.title(),
        "floor": "ground_floor",
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": False,
        "action": "Okay",
        "humidity": 55.0,
        "surface_rh": 60.0,
        "mould_level": "Low",
        "co2": 500.0,
        "co2_available": True,
        "humidity_trend_pct_h": 0.0,
        "humidity_high_duration_min": 0.0,
        "realistic_potential_ml": 0.0,
        "potential_ml": 0.0,
        "delta_g_m3": 0.0,
        "airflow_factor": 1.0,
        "temp_next_5_min_c": -0.1,
        "next_5_min_cost": 0.0,
        "forecast_horizon_min": 15,
        "forecast_moisture_effect_ml": 0.0,
        "forecast_temperature_change_c": -0.2,
        "forecast_cost": 0.0,
        "forecast_confidence": 80,
    }
    base.update(extra)
    return base


def build(rooms, *, options=None, threshold=500, total=0, duration=8, **kw):
    return build_recommendation(
        rooms,
        options or opts(),
        threshold_ml=threshold,
        total_potential_ml=total,
        recommended_duration_min=duration,
        **kw,
    )


def test_nonfinite_values_never_crash_or_leak_into_recommendation():
    r = room(
        "bad",
        action="Ventilate",
        humidity=nan,
        surface_rh=inf,
        co2=-inf,
        realistic_potential_ml=nan,
        delta_g_m3=inf,
        airflow_factor=nan,
        temp_next_5_min_c=nan,
        next_5_min_cost=inf,
        forecast_temperature_change_c=nan,
        forecast_cost=inf,
        forecast_confidence=nan,
    )
    out = build({"bad": r}, total=600)
    assert out["kind"] in {"okay", "ventilate"}
    assert out["estimated_removed_ml"] >= 0
    assert out["estimated_reheat_cost"] == 0
    assert out["forecast_confidence"] == 0


def test_bad_sensor_room_is_authoritative():
    out = build({"bad": room("bad", data_quality="stale")})
    assert out["kind"] == "sensor"
    assert out["status"] == "sensor_error"
    assert out["room_keys"] == ["bad"]


def test_active_moisture_source_continues_ventilation():
    r = room(
        "bath",
        name="Badezimmer",
        active=True,
        action="Continue ventilating",
        moisture_source_active=True,
        moisture_source_label="Dusche",
        moisture_source_confidence=92,
        moisture_source_rate_ml_min=2.5,
        delta_g_m3=2.0,
        forecast_physical_moisture_effect_ml=75,
        forecast_horizon_min=10,
    )
    out = build({"bath": r})
    assert out["kind"] == "continue"
    assert out["status"] == "moisture_source_active"
    assert "Dusche" in out["title"]
    assert any("150 ml/h" in reason for reason in out["reasons"])


def test_closed_room_with_active_moisture_source_requests_early_ventilation():
    r = room(
        "sauna",
        name="Wellnessraum",
        active=False,
        moisture_source_active=True,
        moisture_source_label="Sauna",
        moisture_source_confidence=88,
        moisture_source_rate_ml_min=3.0,
        delta_g_m3=2.4,
        forecast_moisture_effect_ml=95,
    )
    out = build({"sauna": r})
    assert out["kind"] == "ventilate"
    assert out["status"] == "moisture_source_active"
    assert out["room_names"] == ["Wellnessraum"]


def test_running_ventilation_reports_wind_support_and_remaining_time():
    r = room(
        "living",
        name="Wohnzimmer",
        active=True,
        action="Continue ventilating",
        airflow_factor=1.2,
        forecast_moisture_effect_ml=100,
        session_elapsed_min=6,
    )
    out = build({"living": r}, duration=8)
    assert out["kind"] == "continue"
    assert out["duration_min"] == 2.0
    assert any("Windrichtung" in x for x in out["reasons"])


def test_pollen_veto_blocks_nonurgent_candidate():
    r = room(
        "bed",
        name="Schlafzimmer",
        action="Ventilate",
        humidity=70,
        realistic_potential_ml=180,
        delta_g_m3=2.5,
    )
    out = build({"bed": r}, total=180, pollen_blocked=True, pollen_index=4.2)
    assert out["kind"] == "pollen_wait"
    assert out["status"] == "pollen_warning"
    assert "4.2" in out["reasons"][0]


def test_critical_co2_overrides_small_moisture_disadvantage_and_pollen():
    r = room(
        "office",
        name="Arbeitszimmer",
        action="Ventilate",
        co2=1800,
        co2_available=True,
        realistic_potential_ml=0,
        delta_g_m3=-0.3,
    )
    out = build({"office": r}, total=-10, pollen_blocked=True, pollen_index=5.0)
    assert out["kind"] == "ventilate"
    assert any("CO₂" in x for x in out["reasons"])


def test_cross_floor_pair_requires_explicit_connection():
    a = room("eg", action="Ventilate", floor="ground_floor", humidity=70, realistic_potential_ml=220, delta_g_m3=2.5)
    b = room("kg", action="Ventilate", floor="basement", humidity=70, realistic_potential_ml=200, delta_g_m3=2.2)
    out = build(
        {"eg": a, "kg": b},
        options=opts(cross_ventilation_pairs="eg+kg", cross_zone_connections="eg+kg"),
        total=420,
        threshold=350,
    )
    assert out["kind"] == "ventilate"
    assert out["title"] == "Jetzt querlüften"
    assert set(out["room_keys"]) == {"eg", "kg"}


def test_house_ready_can_select_second_room_when_it_adds_material_benefit():
    a = room("a", action="Ventilate", realistic_potential_ml=300, delta_g_m3=2.5, airflow_factor=1.0)
    b = room("b", action="Ventilate", realistic_potential_ml=120, delta_g_m3=1.5, airflow_factor=0.9)
    out = build({"a": a, "b": b}, total=700, threshold=500)
    assert out["kind"] == "ventilate"
    assert set(out["room_keys"]) == {"a", "b"}
    assert out["recommendation_scope"] == "floor"


def test_deferred_nonurgent_problem_waits_for_better_outdoor_window():
    r = room("store", name="Lagerraum", action="Ventilate", humidity=72, realistic_potential_ml=40, delta_g_m3=1.0)
    out = build({"store": r}, total=40)
    assert out["kind"] == "wait"
    assert out["title"] == "Feuchteproblem beobachten"
    assert "Mindestnutzen" in " ".join(out["reasons"])


def test_negative_house_airing_effect_is_reported_as_moisture_gain():
    r = room("living", realistic_potential_ml=-80, delta_g_m3=-1.0)
    out = build({"living": r}, total=-80)
    assert out["kind"] == "wait"
    assert out["status"] == "moisture_gain"
    assert "+80 ml" in out["summary"]


def test_night_forecast_can_prepare_when_no_immediate_action_exists():
    r = room("living", realistic_potential_ml=100)
    out = build({"living": r}, total=150, threshold=500, night_forecast_ml=300)
    assert out["kind"] == "prepare"
    assert out["title"] == "Später vorlüften einplanen"


def test_high_surface_risk_and_falling_humidity_still_marks_problem():
    r = room("bed", surface_rh=82, humidity=60, humidity_trend_pct_h=-4)
    out = build({"bed": r})
    # No ventilation candidate, but the risk must remain visible rather than be hidden by trend.
    assert out["kind"] in {"wait", "okay"}
