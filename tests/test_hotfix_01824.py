from datetime import datetime

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.forecast import (
    in_night_window,
    night_interval_bounds,
    night_window_hours,
    remaining_night_hours,
)
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.recommendation import build_recommendation


def _room_input(*, co2: float, pollen: float = 0.0, humidity: float = 50.0,
                ref_temp: float = 22.0, ref_humidity: float = 55.0) -> RoomInput:
    return RoomInput(
        key="bed",
        name="Schlafzimmer",
        temperature=22.0,
        humidity=humidity,
        reference_temperature=ref_temp,
        reference_humidity=ref_humidity,
        volume_m3=80.0,
        contact_open=False,
        contact_open_seconds=0.0,
        co2=co2,
        pollen_index=pollen,
    )


def test_critical_co2_creates_ventilation_candidate_even_with_slight_moisture_gain():
    options = dict(DEFAULT_OPTIONS)
    room = _room_input(co2=float(options["co2_critical"]) + 400.0)
    result = evaluate_room(room, options, False)

    assert result.delta_g_m3 < 0
    assert result.ventilation_candidate is True
    assert result.action == "Ventilate"


def test_co2_warning_does_not_override_strict_pollen_veto_but_critical_co2_does():
    options = dict(DEFAULT_OPTIONS)
    options.update({"pollen_enabled": True, "pollen_strict_veto": True, "pollen_max": 4.0})

    warning = _room_input(
        co2=float(options["co2_warn"]) + 100.0,
        pollen=8.0,
        humidity=70.0,
        ref_temp=10.0,
        ref_humidity=40.0,
    )
    critical = _room_input(
        co2=float(options["co2_critical"]) + 100.0,
        pollen=8.0,
        humidity=70.0,
        ref_temp=10.0,
        ref_humidity=40.0,
    )

    warning_result = evaluate_room(warning, options, False)
    critical_result = evaluate_room(critical, options, False)

    assert warning_result.ventilation_candidate is True
    assert warning_result.action == "Do not ventilate"
    assert critical_result.ventilation_candidate is True
    assert critical_result.action == "Ventilate"


def test_recommendation_prioritises_critical_co2_despite_small_moisture_disadvantage():
    options = dict(DEFAULT_OPTIONS)
    room = {
        "key": "bed",
        "name": "Schlafzimmer",
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": False,
        "action": "Ventilate",
        "humidity": 50,
        "surface_rh": 55,
        "mould_level": "Low",
        "co2": 1800,
        "co2_available": True,
        "potential_ml": 0,
        "realistic_potential_ml": -30,
        "delta_g_m3": -0.5,
        "airflow_factor": 1.0,
        "temp_next_5_min_c": -0.2,
        "next_5_min_cost": 0.01,
        "forecast_temperature_change_c": -0.4,
        "forecast_cost": 0.02,
        "forecast_confidence": 70,
        "humidity_trend_pct_h": 0,
        "humidity_high_duration_min": 0,
    }

    out = build_recommendation(
        {"bed": room}, options, threshold_ml=500,
        total_potential_ml=-30, recommended_duration_min=7,
        pollen_index=8.0,
    )

    assert out["kind"] == "ventilate"
    assert out["room_names"] == ["Schlafzimmer"]
    text = " ".join(out["reasons"])
    assert "CO₂" in text
    assert "feuchter" in text
    assert "trockener" not in text


def test_night_interval_uses_end_minutes_on_same_hour():
    now = datetime(2026, 9, 11, 7, 15)
    start, end = night_interval_bounds(now, "22:30", "07:30")

    assert start == now
    assert end == datetime(2026, 9, 11, 7, 30)
    assert (end - start).total_seconds() == 15 * 60
    assert abs(remaining_night_hours(now, "22:30", "07:30") - 0.25) < 1e-9


def test_equal_night_start_and_end_disables_night_window_consistently():
    now = datetime(2026, 9, 10, 22, 0)
    start, end = night_interval_bounds(now, "22:00", "22:00")

    assert night_window_hours("22:00", "22:00") == 0.0
    assert remaining_night_hours(now, "22:00", "22:00") == 0.0
    assert in_night_window(now, "22:00", "22:00") is False
    assert start == now
    assert end == now


def test_house_status_prioritises_critical_action_before_cooling():
    from pathlib import Path
    text = Path("custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    urgent = text.index('elif urgent_actionable:')
    cooling = text.index('elif cooling: status = "cooling_recommended"', urgent)
    assert urgent < cooling


def test_equal_night_window_also_disables_evening_notification_path():
    from pathlib import Path
    text = Path("custom_components/freshairiq/notifications.py").read_text(encoding="utf-8")
    assert 'night_window_enabled = night_window_hours(' in text
    assert 'options.get("notify_night") and night_window_enabled and hours_to_night <= 3.0' in text
