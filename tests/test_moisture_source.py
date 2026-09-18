from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.moisture_source import update_moisture_source
from custom_components.freshairiq.recommendation import build_recommendation


def _update(mem, now, ah, ref=8.0, temp=23.0, open_=True, sources=None, volume=40.0):
    return update_moisture_source(
        mem,
        now=now,
        absolute_humidity_g_m3=ah,
        reference_ah_g_m3=ref,
        temperature_c=temp,
        volume_m3=volume,
        window_open=open_,
        learning_rate_per_min=0.03,
        airflow_factor=1.0,
        cross_ventilation=False,
        configured_sources=sources or [],
    )


def test_shower_is_detected_from_absolute_humidity_rise_even_while_window_open():
    mem = {}
    t0 = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    _update(mem, t0, 11.0, open_=True, sources=["shower"])
    out = _update(mem, t0 + timedelta(minutes=5), 12.1, open_=True, sources=["shower"])
    assert out["active"] is True
    assert out["label"] == "Dusche"
    assert out["confidence"] >= 55
    assert out["source_rate_ml_min"] > 0
    # Because ventilation would have reduced moisture, inferred internal
    # generation must be larger than the measured room-water increase alone.
    assert out["generated_ml_window"] > out["observed_change_ml_window"]


def test_normal_sensor_noise_does_not_trigger_source():
    mem = {}
    t0 = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    _update(mem, t0, 11.00, open_=False, sources=["shower", "sauna"])
    out = _update(mem, t0 + timedelta(minutes=5), 11.08, open_=False, sources=["shower", "sauna"])
    assert out["active"] is False
    assert out["confidence"] == 0


def test_active_moisture_source_blocks_premature_close_when_reference_air_is_drier():
    room = RoomInput(
        "wellness", "Wellnessraum", 23, 72, 10, 60, 40, True, 1800,
        session_active=True, session_elapsed_min=30, session_start_temp=24,
        session_start_ah=13.0, learning_rate=0.03, session_fresh_measurements=2,
        moisture_source_active=True, moisture_source_label="Dusche/Sauna",
        moisture_source_confidence=94, moisture_source_rate_ml_min=8.0,
    )
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    assert result.action == "Continue ventilating"
    assert not result.close_recommended
    assert result.moisture_source_active


def test_house_recommendation_explains_active_shower_instead_of_closing():
    rooms = {
        "wellness": {
            "key": "wellness", "name": "Wellnessraum", "calculation_enabled": True,
            "data_quality": "ok", "active": True, "action": "Continue ventilating",
            "close_recommended": False, "humidity": 72, "surface_rh": 75, "mould_level": "Elevated",
            "co2": 500, "delta_g_m3": 5.2, "potential_ml": 44, "realistic_potential_ml": 44,
            "airflow_factor": 1.0, "forecast_horizon_min": 15,
            "forecast_moisture_effect_ml": 63, "forecast_physical_moisture_effect_ml": 66,
            "forecast_temperature_change_c": 0.0, "forecast_cost": 0.0, "forecast_confidence": 95,
            "moisture_source_active": True, "moisture_source_label": "Dusche/Sauna",
            "moisture_source_confidence": 94, "moisture_source_rate_ml_min": 7.5,
        }
    }
    out = build_recommendation(
        rooms, DEFAULT_OPTIONS, threshold_ml=500, total_potential_ml=44,
        recommended_duration_min=15,
    )
    assert out["kind"] == "continue"
    assert out["status"] == "moisture_source_active"
    assert "Dusche/Sauna" in out["title"]
    assert any("Feuchteproduktion" in x for x in out["reasons"])


