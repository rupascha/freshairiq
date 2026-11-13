"""0.26.7.0 F09 (release blocker): source-independent moisture balance.

Support case (summarised, no raw data): kitchen 12 m³, window open 12 min, absolute humidity rose from 10.0 to
10.85 g/m³ although the outdoor air had 6.0 g/m³; a dishwasher was configured but its own signature (warm vapour
burst) did not match – no source was detected and FreshAirIQ said "close". Water rising in a room that is aired
with clearly drier air proves an internal load, whatever it is. Noise, held values and implausible jumps do not.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.moisture_source import update_moisture_source, ventilated_moisture_balance

T0 = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)


def _rh(temp_c: float, ah: float) -> float:
    svp = 6.112 * math.exp(17.62 * temp_c / (243.12 + temp_c))
    return ah * (273.15 + temp_c) / (216.7 * svp) * 100.0


def _run(series, *, ref_ah=6.0, volume=12.0, window=True, configured=("dishwasher",), temp=21.0):
    mem: dict = {}
    states = []
    for minute, ah in enumerate(series):
        states.append(update_moisture_source(
            mem, now=T0 + timedelta(minutes=minute), absolute_humidity_g_m3=ah, reference_ah_g_m3=ref_ah,
            temperature_c=temp, volume_m3=volume, window_open=window, learning_rate_per_min=0.03, airflow_factor=1.0,
            cross_ventilation=False, configured_sources=list(configured)))
    return states


def _kitchen_series():
    return [10.0 + 0.85 * m / 12 for m in range(13)]


def _decide(state, minute, ah, *, ref_ah=6.0, volume=12.0):
    room = RoomInput(key="kueche", name="Küche", temperature=21.0, humidity=_rh(21.0, ah), reference_temperature=8.0,
                     reference_humidity=_rh(8.0, ref_ah), volume_m3=volume, contact_open=True,
                     contact_open_seconds=int(minute * 60), learning_rate=0.03, session_active=True,
                     session_elapsed_min=float(minute), session_fresh_measurements=max(minute // 2, 0),
                     session_target_min=10.0, session_start_ah=10.0, session_start_temp=21.0,
                     moisture_source_active=bool(state["active"]), moisture_source_label=str(state["label"]))
    return evaluate_room(room, DEFAULT_OPTIONS, False)


@pytest.mark.parametrize("configured", [("dishwasher",), (), ("cooking", "dishwasher"), ("shower",)])
def test_the_kitchen_case_is_recognised_whatever_is_configured(configured):
    states = _run(_kitchen_series(), configured=configured)
    final = states[-1]
    assert final["active"] is True
    assert final["generated_ml_window"] >= 4.0 and final["source_rate_ml_min"] >= 0.8
    # not asserted as a named activity: the dishwasher's own signature did not match
    assert final["identified_source"] is None


def test_the_kitchen_case_never_says_close():
    series = _kitchen_series()
    states = _run(series)
    for minute, (ah, state) in enumerate(zip(series, states)):
        if minute < 3:
            continue
        result = _decide(state, minute, ah)
        assert result.action == "Continue ventilating" and not result.close_recommended, (minute, result.reason)
    assert _decide(states[-1], 12, series[-1]).reason.startswith("Active internal moisture source")


def test_the_balance_rule_itself():
    good = dict(ventilated=True, room_ah=10.4, reference_ah=6.0, ah_rise=0.35, interval_min=5.0, generated_ml=12.0,
                source_rate=2.4, volume_m3=12.0, pattern={"samples": 6.0, "ah_monotonic": 1.0, "peak_ah_rate": 0.1})
    assert ventilated_moisture_balance(**good)
    for change in ({"ventilated": False}, {"reference_ah": 10.0}, {"ah_rise": 0.2}, {"ah_rise": 3.5},
                   {"pattern": {"samples": 2.0, "ah_monotonic": 1.0, "peak_ah_rate": 0.1}},
                   {"pattern": {"samples": 6.0, "ah_monotonic": 0.5, "peak_ah_rate": 0.1}},
                   {"pattern": {"samples": 6.0, "ah_monotonic": 1.0, "peak_ah_rate": 2.0}},
                   {"generated_ml": 3.0}, {"source_rate": 0.5}, {"interval_min": 0.0}):
        assert not ventilated_moisture_balance(**{**good, **change}), change


def test_sensor_noise_is_no_source():
    noisy = [10.0 + (0.06 if m % 2 else -0.06) for m in range(13)]
    assert not any(state["active"] for state in _run(noisy))


def test_a_held_value_is_no_source():
    held = [10.0] + [10.4] * 12          # one step, then the sensor repeats the same value
    assert not _run(held)[-1]["active"]


def test_an_implausible_jump_is_no_source():
    jump = [10.0] * 6 + [12.5] + [12.5 + 0.01 * m for m in range(6)]
    assert not any(state["active"] for state in _run(jump))


def test_no_balance_without_airing_or_without_drier_air():
    assert not any(state["active"] for state in _run(_kitchen_series(), window=False))
    assert not any(state["active"] for state in _run(_kitchen_series(), ref_ah=10.3))


def test_people_in_a_large_room_are_no_source():
    slow = [9.0 + 0.1 * m / 12 for m in range(13)]
    assert not any(state["active"] for state in _run(slow, volume=60.0, configured=()))
