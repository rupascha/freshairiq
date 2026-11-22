"""K02 (0.26.7.1): optional per-room close strategy and own temperature limit.

Default (nothing chosen) = the compatible F11 behaviour: helpful drying continues (also after 120 min). A room may
choose "close once the goals are reached" and/or its own temperature limit (empty = inherit the global value). No new
thresholds or durations: ``target_rh``, ``min_duration_min`` and the existing humidity hysteresis are used.
Probe case of the order: small bath 9.4 m³, 14.9 °C / 56 %, outdoor 0.7 °C / 92 % (7.12 vs 4.68 g/m³).
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.localize import Translator
from custom_components.freshairiq.model import (
    GOALS_REACHED_CLOSE_REASON, TEMPERATURE_LIMIT_CLOSE_REASON, VENTILATION_HYSTERESIS_RH, RoomInput, evaluate_room,
)
from custom_components.freshairiq.room_close_strategy import (
    CONF_ROOM_AIRING_MIN_TEMP, CONF_ROOM_CLOSE_STRATEGY, STRATEGY_CONTINUE, STRATEGY_GOALS, close_strategy,
    room_close_options, room_temperature_limit,
)
from custom_components.freshairiq.room_recommendation import _close_reason, _recommendation

BASE = {**DEFAULT_OPTIONS, "target_rh": 58.0, "min_duration_min": 3.0}
GOALS = {CONF_ROOM_CLOSE_STRATEGY: STRATEGY_GOALS}


def _bath(minutes=10.8, rh=56.0, t=14.9, **extra) -> RoomInput:
    values = dict(key="bad", name="Bad", temperature=t, humidity=rh, reference_temperature=0.7, reference_humidity=92.0,
                  volume_m3=9.4, contact_open=True, contact_open_seconds=int(minutes * 60), session_active=True,
                  session_elapsed_min=minutes, session_start_temp=t, learning_rate=0.03, session_fresh_measurements=6)
    values.update(extra)
    return RoomInput(**values)


def _eval(room, cfg=None):
    return evaluate_room(room, room_close_options(BASE, cfg or {}), False)


# ------------------------------------------------------------------------------------------- default and keep drying
# Testvermerk 0.26.7.1 (IQ2, owner decision of 15.11.2026): the default changed. Nothing chosen (and the stored earlier
# default "continue_while_drying", which the form wrote into every saved room) now means "close once the goals are
# reached". The earlier F11 behaviour is the explicit strategy "keep_drying" and is protected here unchanged.

KEEP = {CONF_ROOM_CLOSE_STRATEGY: "keep_drying"}


def test_default_is_the_goal_strategy_and_the_earlier_stored_default_is_no_choice():
    for cfg in ({}, {CONF_ROOM_CLOSE_STRATEGY: "continue_while_drying"}, {CONF_ROOM_CLOSE_STRATEGY: "nonsense", CONF_ROOM_AIRING_MIN_TEMP: "x"}):
        assert close_strategy(cfg) == STRATEGY_GOALS
        assert room_close_options(BASE, cfg)["room_close_on_goals"] is True
    assert close_strategy(KEEP) == "keep_drying" and room_close_options(BASE, KEEP)["room_close_on_goals"] is False
    assert BASE.get("room_close_on_goals") is None                      # the shared options object is never changed


@pytest.mark.parametrize("minutes", [5.0, 10.8, 20.0, 60.0, 120.0])
def test_keep_drying_keeps_helpful_drying_running_up_to_120_minutes(minutes):
    result = _eval(_bath(minutes), KEEP)
    assert result.delta_g_m3 == pytest.approx(2.44, abs=0.05)
    assert result.action == "Continue ventilating" and not result.close_recommended


@pytest.mark.parametrize("minutes,expected", [(2.0, "Continue ventilating"), (3.0, "Close"), (10.8, "Close"), (120.0, "Close")])
def test_default_closes_on_reached_goals_after_the_minimum_duration_not_by_time(minutes, expected):
    assert _eval(_bath(minutes)).action == expected                     # 56 % ≤ target 58 %: reached, never a clock
    assert _eval(_bath(minutes, rh=60.5)).action == "Continue ventilating"   # goal open: keeps airing at any time


# ------------------------------------------------------------------------------------------- goal close

def test_goal_mode_closes_once_the_goals_are_reliably_reached():
    result = _eval(_bath(10.8), GOALS)
    assert result.action == "Close" and result.close_recommended and result.reason == GOALS_REACHED_CLOSE_REASON
    text = _close_reason(result, room_close_options(BASE, GOALS))
    assert text.startswith("Die Ziele dieses Raums sind erreicht (Luftfeuchte höchstens 58 %)")
    assert Translator().text(text).startswith("The goals of this room are reached (humidity at most 58 %)")


def test_goal_mode_waits_for_the_rooms_own_minimum_duration():
    # a window opened later has its own session clock: 2 minutes < min_duration_min 3 → no close yet
    assert _eval(_bath(2.0), GOALS).action == "Continue ventilating"
    assert _eval(_bath(3.0), GOALS).action == "Close"


def test_goal_not_reached_keeps_airing_and_rounding_never_fakes_it():
    assert _eval(_bath(rh=58.4), GOALS).action == "Continue ventilating"      # would display as 58 %
    assert _eval(_bath(rh=58.0), GOALS).action == "Close"


def test_missing_or_stale_readings_allow_no_invented_success():
    assert _eval(_bath(session_fresh_measurements=0), GOALS).action == "Continue ventilating"
    assert _eval(_bath(measurements_stale=True), GOALS).action == "Continue ventilating"


@pytest.mark.parametrize("extra", [
    dict(moisture_source_active=True, moisture_source_label="Dusche"),
    dict(moisture_source_recovery=True, moisture_source_ended_min=1.0),
])
def test_active_or_following_moisture_source_prevents_the_goal_close(extra):
    result = _eval(_bath(**extra), GOALS)
    assert result.action == "Continue ventilating" and not result.close_recommended


def test_co2_need_keeps_the_room_open_in_goal_mode():
    options = room_close_options({**BASE, "co2_warn": 1000}, GOALS)
    result = evaluate_room(_bath(co2=1180.0), options, False)
    assert result.action != "Close"
    assert evaluate_room(_bath(co2_sensor_missing=True), options, False).action != "Close"


def test_goal_close_is_session_stable_while_the_outdoor_air_stays_drier():
    # Testvermerk 0.26.7.1 (B3): the stored close now carries its cause (close_notified_kind); this test models a session
    # whose goals were really reached – a stored close of another cause no longer counts as a reached goal (B3 tests)
    stored = _eval(_bath(20.0, close_notified=True, close_notified_kind="goals_reached"), GOALS)
    assert stored.close_recommended                               # not lifted because the air is still drier
    within = _eval(_bath(20.0, rh=58.0 + VENTILATION_HYSTERESIS_RH, close_notified=True, close_notified_kind="goals_reached"), GOALS)
    assert within.close_recommended                               # inside the existing hysteresis band: stays
    reopened = _eval(_bath(20.0, rh=58.0 + VENTILATION_HYSTERESIS_RH + 1.0, close_notified=True, close_notified_kind="goals_reached"), GOALS)
    assert not reopened.close_recommended                         # a new humidity load opens the goal again


def test_reason_is_honest_when_the_air_no_longer_helps_anyway():
    result = _eval(_bath(rh=36.0, t=14.9), GOALS)   # room as dry as the outdoor air
    assert result.delta_g_m3 <= BASE["close_delta"]
    assert result.action == "Close" and result.reason != GOALS_REACHED_CLOSE_REASON


# ------------------------------------------------------------------------------------------- temperature limit

def test_room_limit_inherits_overrides_and_switches_off_the_global_value():
    assert room_temperature_limit({}) is None and room_temperature_limit({CONF_ROOM_AIRING_MIN_TEMP: ""}) is None
    assert room_temperature_limit({CONF_ROOM_AIRING_MIN_TEMP: 16}) == 16.0
    assert room_temperature_limit({CONF_ROOM_AIRING_MIN_TEMP: 0}) == 0.0
    for bad in (True, "x", float("nan"), -1, 31):
        assert room_temperature_limit({CONF_ROOM_AIRING_MIN_TEMP: bad}) is None
    glob = {**BASE, "airing_min_room_temp_c": 15.0}
    assert room_close_options(glob, {})["airing_min_room_temp_c"] == 15.0                       # inherited
    assert room_close_options(glob, {CONF_ROOM_AIRING_MIN_TEMP: 0})["airing_min_room_temp_c"] == 0.0   # none here
    assert close_strategy({}) == STRATEGY_GOALS      # Testvermerk 0.26.7.1 (IQ2): new default, see above


def test_clearly_undershot_room_limit_closes_with_the_temperature_reason():
    cfg = {CONF_ROOM_AIRING_MIN_TEMP: 16.0}
    result = _eval(_bath(30.0, rh=70.0), cfg)
    assert result.action == "Close" and result.reason == TEMPERATURE_LIMIT_CLOSE_REASON
    text = _close_reason(result, room_close_options(BASE, cfg))
    assert "16.0 °C" in text and "nicht weil genug Feuchtigkeit entfernt wurde" in text
    # the global limit alone (0 = none) and an explicit room "0" never close here
    assert _eval(_bath(30.0, rh=70.0)).action == "Continue ventilating"
    assert _eval(_bath(30.0, rh=70.0), {CONF_ROOM_AIRING_MIN_TEMP: 0}).action == "Continue ventilating"


def test_critical_co2_keeps_priority_over_the_room_temperature_limit():
    options = room_close_options({**BASE, "co2_warn": 1000, "co2_critical": 1400}, {CONF_ROOM_AIRING_MIN_TEMP: 16.0})
    result = evaluate_room(_bath(30.0, rh=70.0, co2=1600.0), options, False)
    action, _reason, reasons = _recommendation(result, options, pollen=0.0, co2=1600.0, airflow=1.0, wind_bearing=None, wind_speed=None)
    assert action != "Close" or any("CO₂" in r for r in reasons)   # the conflict is explained, never silent
