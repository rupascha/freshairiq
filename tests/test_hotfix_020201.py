from pathlib import Path

from custom_components.freshairiq.forecast import horizon_forecast

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")


def _common():
    return dict(
        current_ah=12.0,
        source_ah=6.0,
        current_temp_c=21.0,
        source_temp_c=10.0,
        volume_m3=100.0,
        rate_per_min=0.03,
        airflow_bonus=1.0,
    )


def test_long_horizon_is_rolling_five_minute_simulation_but_five_minute_gate_is_single_step():
    f5 = horizon_forecast(horizon_min=5, **_common())
    f60 = horizon_forecast(horizon_min=60, **_common())
    assert f5["simulation_steps"] == 1
    assert f5["method"].startswith("hybrid_")
    assert f60["simulation_steps"] == 12
    assert f60["method"].startswith("rolling_")
    assert f60["simulated_final_ah"] < 12.0
    assert f60["simulated_final_ah"] > 6.0


def test_future_weather_boundary_changes_the_60_minute_result():
    stable = horizon_forecast(horizon_min=60, **_common())
    # Outdoor air becomes progressively moister and warmer over the hour.
    future = {
        minute: {
            "absolute_humidity": 6.0 + (5.0 * minute / 60.0),
            "temperature_c": 10.0 + (9.0 * minute / 60.0),
            "confidence": 88,
        }
        for minute in range(5, 65, 5)
    }
    changing = horizon_forecast(horizon_min=60, future_source_boundaries=future, **_common())
    assert changing["future_weather_used"] is True
    assert changing["future_weather_confidence"] == 88
    assert changing["confidence"] <= 88
    assert changing["uncapped_physical_moisture_effect_ml"] < stable["uncapped_physical_moisture_effect_ml"]
    assert changing["temperature_change_c"] > stable["temperature_change_c"]


def test_internal_moisture_is_carried_into_following_simulation_steps():
    dry = horizon_forecast(horizon_min=60, prior_source_ml_min=0.0, **_common())
    source = horizon_forecast(horizon_min=60, prior_source_ml_min=4.0, **_common())
    # Generated moisture raises the simulated room AH and can therefore be
    # exchanged again in later steps. The end state must reflect that evolution.
    assert source["simulated_final_ah"] > dry["simulated_final_ah"]
    assert source["internal_moisture_effect_ml"] > 0


def test_coordinator_supplies_weather_steps_only_for_outdoor_reference_rooms():
    assert 'delays=tuple(range(5, 121, 5))' in COORD
    assert 'future_source_boundaries=(' in COORD
    assert 'if not cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE)' in COORD
    assert 'and not cfg.get(CONF_ROOM_REFERENCE_HUMIDITY)' in COORD
    assert '"forecast_simulation_steps"' in COORD
    assert '"forecast_future_weather_used"' in COORD
