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




def test_four_person_like_slow_humidity_load_is_not_mislabelled_as_cooking():
    """Occupancy-like moisture must not become cooking just because cooking is configured."""
    mem = {}
    t0 = datetime(2026, 9, 29, 17, 0, tzinfo=timezone.utc)
    _update(mem, t0, 10.00, temp=22.0, open_=False, sources=["cooking"], volume=45.0)
    _update(mem, t0 + timedelta(minutes=3), 10.12, temp=22.05, open_=False, sources=["cooking"], volume=45.0)
    out = _update(mem, t0 + timedelta(minutes=6), 10.27, temp=22.10, open_=False, sources=["cooking"], volume=45.0)
    assert out["active"] is False
    assert out["identified_source"] is None
    assert out["label"] == "Kochen"  # configured context may be displayed while inactive


def test_cooking_requires_combined_heat_and_moisture_pattern():
    mem = {}
    t0 = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)
    _update(mem, t0, 10.0, temp=21.8, open_=False, sources=["cooking"], volume=45.0)
    _update(mem, t0 + timedelta(minutes=3), 10.35, temp=22.1, open_=False, sources=["cooking"], volume=45.0)
    out = _update(mem, t0 + timedelta(minutes=6), 10.72, temp=22.35, open_=False, sources=["cooking"], volume=45.0)
    assert out["active"] is True
    assert out["identified_source"] == "cooking"
    assert out["label"] == "Kochen"


def test_sauna_requires_heat_plus_real_water_not_heat_alone():
    mem = {}
    t0 = datetime(2026, 9, 29, 19, 0, tzinfo=timezone.utc)
    _update(mem, t0, 10.0, temp=22.0, open_=False, sources=["sauna"], volume=40.0)
    out = _update(mem, t0 + timedelta(minutes=5), 10.06, temp=24.0, open_=False, sources=["sauna"], volume=40.0)
    assert out["active"] is False
    assert out["identified_source"] is None


def test_ambiguous_shower_and_bath_pattern_does_not_claim_exact_activity():
    mem = {}
    t0 = datetime(2026, 9, 29, 20, 0, tzinfo=timezone.utc)
    sources = ["shower", "bath"]
    _update(mem, t0, 10.0, temp=22.0, open_=False, sources=sources, volume=40.0)
    _update(mem, t0 + timedelta(minutes=3), 10.5, temp=22.15, open_=False, sources=sources, volume=40.0)
    out = _update(mem, t0 + timedelta(minutes=6), 11.0, temp=22.3, open_=False, sources=sources, volume=40.0)
    assert out["active"] is True
    assert out["identified_source"] is None
    assert out["label"] == "Feuchtequelle"
    assert out["ambiguous"] is True


def test_washing_machine_context_alone_never_proves_washing_machine_from_climate():
    mem = {}
    t0 = datetime(2026, 9, 29, 21, 0, tzinfo=timezone.utc)
    _update(mem, t0, 10.0, temp=22.0, open_=False, sources=["washing_machine"], volume=30.0)
    out = _update(mem, t0 + timedelta(minutes=5), 10.5, temp=22.2, open_=False, sources=["washing_machine"], volume=30.0)
    assert out["active"] is False
    assert out["identified_source"] is None


def test_pattern_features_defensively_ignore_old_broken_and_non_numeric_rows():
    from custom_components.freshairiq import moisture_source as ms
    now = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)
    assert ms._pattern_features([], now=now)["samples"] == 0
    points = [
        {"at": "broken", "ah": 10, "temp": 22},
        {"at": (now - timedelta(minutes=20)).isoformat(), "ah": 9, "temp": 21},
        {"at": (now - timedelta(minutes=5)).isoformat(), "ah": "bad", "temp": 22},
        {"at": (now - timedelta(minutes=4)).isoformat(), "ah": 10.0, "temp": 22.0},
        {"at": (now - timedelta(minutes=2)).isoformat(), "ah": 10.2, "temp": 22.1},
    ]
    out = ms._pattern_features(points, now=now)
    assert out["samples"] == 2
    assert out["ah_monotonic"] == 1.0
    assert out["peak_ah_rate"] > 0


def test_source_signature_matrix_covers_sauna_dryer_and_ironing_without_guessing_washer():
    from custom_components.freshairiq import moisture_source as ms
    from custom_components.freshairiq.const import (
        MOISTURE_SOURCE_DRYER, MOISTURE_SOURCE_IRONING_STATION,
        MOISTURE_SOURCE_SAUNA, MOISTURE_SOURCE_WASHING_MACHINE,
    )
    pattern = {"samples": 3.0, "ah_monotonic": 1.0, "temp_monotonic": 1.0, "peak_ah_rate": 0.2}
    sauna = ms._source_signatures({MOISTURE_SOURCE_SAUNA}, ah_rise=.2, temp_rise=1.0, source_rate=3.0, generated_ml=18, pattern=pattern)
    dryer = ms._source_signatures({MOISTURE_SOURCE_DRYER}, ah_rise=.2, temp_rise=.7, source_rate=3.2, generated_ml=18, pattern=pattern)
    ironing = ms._source_signatures({MOISTURE_SOURCE_IRONING_STATION}, ah_rise=.4, temp_rise=.3, source_rate=4.5, generated_ml=25, pattern=pattern)
    washer = ms._source_signatures({MOISTURE_SOURCE_WASHING_MACHINE}, ah_rise=.8, temp_rise=.8, source_rate=8, generated_ml=50, pattern=pattern)
    assert sauna == [MOISTURE_SOURCE_SAUNA]
    assert dryer == [MOISTURE_SOURCE_DRYER]
    assert ironing == [MOISTURE_SOURCE_IRONING_STATION]
    assert washer == []
