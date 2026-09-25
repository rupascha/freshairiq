from pathlib import Path

import pytest

from custom_components.freshairiq.energy import ventilation_cost_for_temperature_path
from custom_components.freshairiq.forecast import horizon_forecast
from custom_components.freshairiq.passive_ventilation import evaluate_passive_ventilation

ROOT = Path(__file__).resolve().parents[1]


def test_rolling_energy_uses_future_step_temperatures():
    opts = {"heating_system": "gas", "gas_price_per_kwh": 0.11, "gas_efficiency": 0.92}
    colder = [
        {"duration_min": 5, "room_start_c": 21, "source_c": 10},
        {"duration_min": 5, "room_start_c": 20, "source_c": 8},
    ]
    milder = [
        {"duration_min": 5, "room_start_c": 21, "source_c": 10},
        {"duration_min": 5, "room_start_c": 20, "source_c": 18},
    ]
    assert ventilation_cost_for_temperature_path(80, 0.03, 1.0, colder, opts)[2] > ventilation_cost_for_temperature_path(80, 0.03, 1.0, milder, opts)[2]


def test_long_forecast_close_time_can_be_limited_by_cumulative_cooling():
    f = horizon_forecast(
        current_ah=14, source_ah=7, current_temp_c=20, source_temp_c=0,
        volume_m3=80, rate_per_min=0.04, airflow_bonus=1.0, horizon_min=60,
        min_return_next_5_min_ml=0, max_temp_loss_next_5_min_c=0.6,
        min_efficiency_ml_per_01c=0, min_duration_min=3, max_duration_min=120,
        future_source_boundaries={m: {"absolute_humidity": 7, "temperature_c": 0, "confidence": 90} for m in range(5, 65, 5)},
    )
    assert f["optimal_close_in_min"] is not None
    assert f["optimal_close_reason"] in {"cumulative_temperature_loss", "projected_end_temperature"}
    assert f["temperature_path"]


def test_passive_requires_stable_multi_sample_trend_and_start_reference():
    good = evaluate_passive_ventilation(
        start_ah=12, current_ah=11.7, reference_ah=6.3, start_reference_ah=6.0,
        volume_m3=100, elapsed_min=6, connected=True, connection_strength=1.0,
        samples=[
            {"elapsed_min": 0, "ah": 12.0},
            {"elapsed_min": 2, "ah": 11.93},
            {"elapsed_min": 4, "ah": 11.82},
        ],
    )
    noisy = evaluate_passive_ventilation(
        start_ah=12, current_ah=11.7, reference_ah=6.3, start_reference_ah=6.0,
        volume_m3=100, elapsed_min=6, connected=True, connection_strength=0.65,
        samples=[
            {"elapsed_min": 0, "ah": 12.0},
            {"elapsed_min": 2, "ah": 11.75},
            {"elapsed_min": 4, "ah": 12.05},
        ],
    )
    assert good["active"] is True
    assert noisy["active"] is False


def test_house_mode_is_aggregate_not_presentation_only():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'house_should_close' in coordinator
    assert 'house_next5_removed' in coordinator
    assert '"room_keys"] = active_room_keys' in coordinator
    assert '"selected_rooms": []' in coordinator
    assert 'len(intelligent_recommendation.get("room_keys") or []) < len(active)' not in coordinator


def test_release_version_020205():
    assert 'VERSION = "0.25.0.70"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.70"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.70";' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
