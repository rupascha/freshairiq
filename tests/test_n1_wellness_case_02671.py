"""N1 (0.26.7.1): "keep ventilating" with goal reached, 0 ml for the next 15 minutes and "0 min – target reached".

The 0 ml shown is the forecast *limited at the humidity target* – not "no physical benefit": the uncapped physical
path of the same forecast still removes moisture. The card therefore names both values; the IQ time shows "0 min" only
for a real close and "being reassessed" for a running airing past its planned time; the live coach names the measured
reason instead of a standing positive phrase. The decision rules themselves are unchanged (F11: the default strategy
keeps drying while the air helps; it closes when the air no longer helps, at the explicit temperature limit, on
moisture coming in, or – opted in – once the goals are reliably reached). All fixtures are synthetic.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.forecast import horizon_forecast
from custom_components.freshairiq.live_coach import refine_live_recommendation
from custom_components.freshairiq.localize import Translator
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.room_close_strategy import room_close_options
from custom_components.freshairiq.room_recommendation import _recommendation

ARGS = dict(current_ah=9.0, source_ah=5.0, current_temp_c=20.0, source_temp_c=5.0, volume_m3=48.3, rate_per_min=0.03,
            airflow_bonus=1.0, horizon_min=15.0, target_ah=9.5, running=True, session_elapsed_min=40.0,
            session_fresh_measurements=6)


def test_target_limited_zero_is_not_physical_zero():
    capped = horizon_forecast(**ARGS, cap_positive_to_target=True)
    uncapped = horizon_forecast(**ARGS, cap_positive_to_target=False)
    assert capped["moisture_effect_ml"] == 0 and capped["target_limited"] is True
    assert capped["uncapped_physical_moisture_effect_ml"] > 0
    assert uncapped["moisture_effect_ml"] == capped["uncapped_physical_moisture_effect_ml"]


DEHUMIDIFY = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "target_rh": 58.0, "min_duration_min": 3.0}


def _room(**extra):
    values = dict(key="w", name="W", temperature=20.0, humidity=55.0, reference_temperature=5.0, reference_humidity=84.4,
                  volume_m3=48.3, contact_open=True, contact_open_seconds=2400, session_active=True,
                  session_elapsed_min=40.0, session_start_temp=20.4, session_fresh_measurements=6)
    values.update(extra)
    return RoomInput(**values)


def _decide(room, options=DEHUMIDIFY, co2=None, latched=False):
    result = evaluate_room(room, options, False)
    return result, _recommendation(result, options, pollen=0.0, co2=co2, airflow=1.0, wind_bearing=None, wind_speed=None,
                                   co2_latched=latched)[0]


def test_goal_reached_but_air_still_helps_keeps_drying_in_the_default_strategy():
    result, action = _decide(_room())
    assert result.delta_g_m3 > 0.4 and action == "Continue ventilating"


def test_goal_reached_closes_in_the_chosen_goal_strategy():
    options = room_close_options(DEHUMIDIFY, {"close_strategy": "goals_reached"})
    result, action = _decide(_room(), options)
    assert action == "Close" and result.close_kind == "goals_reached"


def test_real_uselessness_closes():
    result, action = _decide(_room(reference_temperature=12.0, reference_humidity=95.0))
    assert result.delta_g_m3 <= 0.4 and action == "Close" and result.close_kind == "air_no_longer_helps"


def test_stale_readings_never_give_an_invented_goal_close():
    options = room_close_options(DEHUMIDIFY, {"close_strategy": "goals_reached"})
    for room in (_room(session_fresh_measurements=0), _room(measurements_stale=True)):
        assert _decide(room, options)[0].close_kind != "goals_reached"


def test_temperature_limit_closes_even_when_the_air_still_helps():
    result, action = _decide(_room(temperature=15.5), {**DEHUMIDIFY, "airing_min_room_temp_c": 16.0})
    assert action == "Close" and result.close_kind == "temperature_limit"


def test_co2_alone_and_critical_co2_keep_their_priority():
    options = {**DEHUMIDIFY, "co2_warn": 1000.0, "co2_critical": 1400.0, "airing_min_room_temp_c": 16.0}
    dry = _room(humidity=40.0, reference_temperature=18.0, reference_humidity=60.0)      # no moisture benefit
    assert _decide(replace(dry, co2=1100.0), options, co2=1100.0)[1] != "Close"
    critical = _decide(replace(_room(temperature=15.5), co2=1600.0), options, co2=1600.0)
    assert critical[0].close_kind != "temperature_limit" and critical[1] == "Continue ventilating"


# ------------------------------------------------------------------------------------------------ live coach reason

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 5, "max_duration_min": 20}


def _coach_room(elapsed, **extra):
    room = {"key": "w", "name": "W", "floor": "eg", "calculation_enabled": True, "data_quality": "ok", "active": True,
            "opening_state": "open", "session_elapsed_min": elapsed, "close_decision_ready": True, "volume_m3": 48.0,
            "moisture_effect_next_5_min_ml": 40.0, "forecast_5_min_net_moisture_change_ml": 40.0, "delta_g_m3": 2.9,
            "temperature_change_c": -0.4, "close_recommended": False, "action": "Continue ventilating",
            "goal_state": {"hard_close": False, "goals": []}, "session_recommended_duration_min": 20.0}
    room.update(extra)
    return room


def test_past_the_planned_time_the_coach_names_the_measured_reason():
    out = refine_live_recommendation({"w": _coach_room(60.0)}, OPTIONS, {"kind": "continue", "room_keys": ["w"], "duration_min": 20.0})
    assert out["kind"] == "continue" and out["live_coach_time_state"] == "reassessing" and out["live_coach_remaining_min"] is None
    reason = out["live_coach_reason"]
    assert reason.startswith("Geplante Zeit erreicht; die Außenluft ist noch 2.9 g/m³ trockener (nächste 5 min etwa 40 ml)")
    assert "Raum -0.4 °C seit Start" in reason and out["reasons"][0] == reason
    assert Translator().text(reason).startswith("Planned time reached; the outdoor air is still 2.9 g/m³ drier")


def test_inside_the_planned_time_the_countdown_and_its_reason_stay():
    out = refine_live_recommendation({"w": _coach_room(3.0)}, OPTIONS, {"kind": "continue", "room_keys": ["w"], "duration_min": 20.0})
    assert out["live_coach_time_state"] == "countdown" and not out["live_coach_reason"].startswith("Geplante Zeit erreicht")


@pytest.mark.parametrize("next5,expected", [(0.4, "0 ml"), (0.6, "1 ml")])
def test_rounding_of_a_small_benefit_is_shown_as_measured(next5, expected):
    out = refine_live_recommendation({"w": _coach_room(60.0, moisture_effect_next_5_min_ml=next5,
                                                       forecast_5_min_net_moisture_change_ml=next5)},
                                     OPTIONS, {"kind": "continue", "room_keys": ["w"], "duration_min": 20.0})
    # a rounded "0 ml" is shown as such, but the air is still clearly drier – the reason says both, it never claims a goal
    assert f"etwa {expected}" in out["live_coach_reason"] and "Ziel erreicht" not in out["live_coach_reason"]
