"""0.26.7.0 support case C: the close advice came too early with dehumidification as the priority.

Summarised evidence only (no raw sessions): operating_profile=dehumidify, start/high/target 62/68/58 %, min_delta
2.5 / 1.5 g/m³, close_delta 0.4 g/m³, 3–20 min, min_return 25 ml, source follow-up 8 min; the user saw a lot of
water still leaving after the close advice. Cause found in the code: the sliding humidity plateau ("did not fall
for 15 min") closed while the reference air was still clearly drier and the physical 5-minute return was well
above the limit – a moisture load inside the room (often not yet recognised as a source) ate the drying.

Hard limits (moisture coming in; since F11 the explicit temperature limit instead of a maximum duration, critical temperature loss, protection) stay separate from the
soft ones (plateau, small return) and are unchanged; no threshold was changed.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room

CASE = {**DEFAULT_OPTIONS, "operating_profile": "dehumidify", "start_rh": 62.0, "high_rh": 68.0, "target_rh": 58.0,
        "min_delta": 2.5, "min_delta_high_rh": 1.5, "close_delta": 0.4, "min_duration_min": 3.0, "max_duration_min": 20.0,
        "min_return_next_5_min_ml": 25.0, "repeat_recommendation_cooldown_min": 20.0, "moisture_source_postrun_min": 8.0}
COMFORT = {**CASE, "operating_profile": "comfort"}


def _room(**extra) -> RoomInput:
    """Bathroom-sized room, window open 12 min, outdoor air clearly drier, humidity flat for 15 min."""
    values = dict(key="bad", name="Bad", temperature=21.0, humidity=63.0, reference_temperature=8.0, reference_humidity=70.0,
                  volume_m3=20.0, contact_open=True, contact_open_seconds=720, learning_rate=0.05, session_active=True,
                  session_elapsed_min=12.0, session_fresh_measurements=6, session_target_min=10.0,
                  session_start_ah=absolute_humidity(21.0, 63.5), session_start_temp=21.2, humidity_plateau=True)
    values.update(extra)
    return RoomInput(**values)


def _closes(room: RoomInput, options=CASE, cross: bool = False) -> bool:
    return evaluate_room(room, options, cross).action == "Close"


def test_flat_humidity_with_a_hidden_load_keeps_the_window_open_when_drying_is_the_priority():
    assert not _closes(_room())
    # Testvermerk 0.26.7.0 (F11): the plateau no longer closes in any profile while the outdoor air still dries – the
    # comfort profile now keeps the window open as well (previously: plateau closes)
    assert not _closes(_room(), COMFORT)


def test_humidity_rising_although_aired_does_not_close():
    room = _room(humidity=64.5, session_start_ah=absolute_humidity(21.0, 63.0))
    assert not _closes(room)


def test_recognised_source_and_its_follow_up_keep_it_open_as_before():
    assert not _closes(_room(moisture_source_active=True), COMFORT)
    assert not _closes(_room(moisture_source_recovery=True, moisture_source_ended_min=3.0), COMFORT)
    # recognised only later: from that moment on it is a source – the same decision
    assert not _closes(_room(moisture_source_active=True, session_elapsed_min=16.0))


def test_after_the_target_or_minimum_duration_positive_drying_continues():
    below_target = _room(humidity=57.0, session_start_ah=absolute_humidity(21.0, 57.2))
    assert not _closes(below_target)
    assert not _closes(_room(session_elapsed_min=3.5))


def test_plateau_still_closes_when_the_physical_return_has_really_fallen():
    # reference air almost as moist as the room: the equilibrium case the plateau was made for
    # Testvermerk 0.26.7.0 (F11): 20 °C / 62 % is still ~0.9 g/m³ drier than the room and keeps drying; the
    # equilibrium is reached at 20 °C / 66 % (difference below close_delta) – there it closes in every profile.
    assert not _closes(_room(reference_temperature=20.0, reference_humidity=62.0))
    near_equilibrium = _room(reference_temperature=20.0, reference_humidity=66.0)
    assert _closes(near_equilibrium) and _closes(near_equilibrium, COMFORT)


@pytest.mark.parametrize("extra", [
    # Testvermerk 0.26.7.0 (F11): the maximum duration is no longer a hard limit – replaced by the user's explicit
    # temperature limit (cold outdoor air cools the room to 17.5 °C, limit 18 °C)
    {"temperature": 17.5, "session_elapsed_min": 20.5, "contact_open_seconds": 1230, "options": {"airing_min_room_temp_c": 18.0}},
    {"reference_temperature": 21.0, "reference_humidity": 75.0},                 # moisture would come in
])
def test_hard_limits_close_unchanged(extra):
    extra = dict(extra)
    options = {**CASE, **extra.pop("options", {})}
    assert _closes(_room(**extra), options)


def test_f11_no_time_limit_for_the_support_case():
    for minutes in (5.0, 10.0, 20.0, 20.5, 30.0, 60.0, 120.0):
        room = _room(session_elapsed_min=minutes, contact_open_seconds=int(minutes * 60))
        assert not _closes(room), minutes
        assert not _closes(room, COMFORT), minutes


def test_several_windows_cross_ventilation_and_an_exhaust_fan():
    assert not _closes(_room(), cross=True)                                       # several windows / cross ventilation
    fan = _room(contact_open=False, mechanical_only=True)                         # bathroom aired by its fan only
    result = evaluate_room(fan, CASE, False)
    assert result.action != "Close"


# ----------------------------------------------------------------------------------------------- close_time_mae_min

def _aligned(close_min, duration=14.0):
    from custom_components.freshairiq.forecast_validation import build_validation_record
    session = {"key": "bad", "name": "Bad", "prediction_comparable": True, "prediction_time_aligned": True,
               "predicted_removed_ml": 80, "removed_ml": 90, "predicted_temperature_change_c": -0.4, "temp_delta_c": -0.3,
               # the replay horizon is set to the measured duration at the end – the old error was always 0.0
               "prediction_horizon_min": duration, "validation_duration_min": duration, "prediction_close_min": close_min,
               "prediction_confidence": 80}
    result = {"started_at": "2026-11-13T18:00:00+01:00", "ended_at": "2026-11-13T18:14:00+01:00", "removed_ml": 90, "duration_min": duration}
    return build_validation_record(result, [session], model_version="0.26.7.0")


def test_close_time_error_compares_the_close_time_predicted_at_the_start():
    record = _aligned(10.0)
    assert record["close_time_mae_min"] == 4.0
    assert record["room_results"][0]["close_time_error_min"] == 4.0
    assert record["room_results"][0]["forecast_horizon_min"] == 14.0      # the replay horizon itself is unchanged


def test_no_close_time_prediction_means_no_error_not_a_perfect_zero():
    record = _aligned(None)
    assert record["close_time_mae_min"] is None
    assert record["room_results"][0]["close_time_error_min"] is None


@pytest.mark.parametrize("options", [CASE, COMFORT])
def test_rule_recognised_load_and_drier_air_never_get_an_ordinary_close(options):
    """Owner rule: a reliably recognised internal load + still drier outdoor air -> no ordinary close because of the
    target, the plateau, a forecast error or a small predicted return. Hard limits stay separate (next test)."""
    below_target = dict(humidity=57.0, session_start_ah=absolute_humidity(21.0, 57.2))
    small_return = dict(learning_rate=0.004)          # predicted 5-minute return far below the soft limit
    for extra in ({}, below_target, small_return, {**below_target, **small_return}):
        assert not _closes(_room(moisture_source_active=True, **extra), options), extra


def test_rule_hard_limits_still_apply_with_a_recognised_load():
    # moisture coming in is protection, not an ordinary close – the source keeps no window open against it
    assert _closes(_room(moisture_source_active=True, reference_temperature=21.0, reference_humidity=75.0))
