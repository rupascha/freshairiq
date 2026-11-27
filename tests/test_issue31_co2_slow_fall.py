"""#31: a CO2 airing whose CO2 levels off above the release level is given up instead of running forever.

Pure rule (``co2_airing_given_up``) and slope (``co2_slope_ppm_min``); the coordinator releases the hold band with them.
"""
from __future__ import annotations

import random

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.co2_fall import CO2_GIVE_UP_HOLD_S, co2_airing_given_up, co2_give_up_confirmed, co2_slope_ppm_min
from custom_components.freshairiq.model import CO2_SLOW_FALL_CLOSE_REASON, RoomInput, evaluate_room
from custom_components.freshairiq.room_recommendation import _close_reason

OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400, "co2_release": 600, "min_duration_min": 3}
SEED = 1  # picked: with the hold it is never given up, without it one noisy slope is enough
ISSUE_SERIES = [(0, 1150), (60, 980), (180, 790), (300, 715), (360, 698), (480, 683), (720, 680)]


@pytest.mark.parametrize(("co2", "slope", "given_up"), [
    (700, None, False),    # slope unknown: keep airing
    (700, 11, False),      # climbing again
    (700, 10, True),       # boundary: not climbing "again"
    (700, 5, True),        # stalled but not climbing hard
    (700, 0, True),        # flat
    (700, -21, False),     # clear fall
    (700, -50 / 3, True),  # 100 ppm at 16.7 ppm/min = 6 min
    (640, -20, False),     # 40 ppm at 20 ppm/min = exactly 2 min: still airing
    (641, -20, True),      # just over 2 min
    (600, -1, False),      # at the release level the normal release applies
    (1000, 0, False),      # above the warning threshold the rule does not apply
    (550, 0, False),       # below the release level there is nothing to hold
])
def test_rule_table(co2, slope, given_up):
    assert co2_airing_given_up(co2, OPTIONS, slope, 10.0, -170.0) is given_up


@pytest.mark.parametrize(("slope", "steepest", "given_up"), [
    (-19, -23, False),   # a slow steady fall has not flattened
    (-5, -23, True),     # flattened to under a quarter of the steepest fall
    (-5.75, -23, True),  # exactly a quarter
    (0, 0, True),        # a stall with no fall at all counts as flattened
])
def test_only_a_flattened_fall_is_given_up(slope, steepest, given_up):
    assert co2_airing_given_up(700, OPTIONS, slope, 10.0, steepest) is given_up


def test_automatic_release_uses_the_warning_threshold_minus_50():
    options = {**OPTIONS, "co2_release": 0}
    assert co2_airing_given_up(960, options, 0, 10.0, 0.0) is True
    assert co2_airing_given_up(940, options, 0, 10.0, 0.0) is False


def test_min_duration_wins():
    assert co2_airing_given_up(700, OPTIONS, 0, 2.9, 0.0) is False
    assert co2_airing_given_up(700, OPTIONS, 0, 3.0, 0.0) is True


def test_slope_needs_two_samples_and_a_minute():
    assert co2_slope_ppm_min([]) is None
    assert co2_slope_ppm_min([(0, 800)]) is None
    assert co2_slope_ppm_min([(0, 800), (59, 790)]) is None
    assert co2_slope_ppm_min([(0, 800), (60, 790)]) == pytest.approx(-10)


def test_slope_uses_only_the_last_two_minutes_and_fits_the_line():
    assert co2_slope_ppm_min([(0, 2000), (60, 1500), (200, 900), (260, 880), (320, 860)]) == pytest.approx(-20)


def _running(**extra) -> RoomInput:
    values = dict(key="sz", name="Schlafzimmer", temperature=21.0, humidity=50.0, reference_temperature=12.0,
                  reference_humidity=55.0, volume_m3=40.0, contact_open=True, contact_open_seconds=600.0,
                  learning_rate=0.03, co2=698.0, session_active=True, session_elapsed_min=10.0, session_co2_only=True,
                  session_fresh_measurements=3)
    values.update(extra)
    return RoomInput(**values)


GOALS = {**OPTIONS, "room_close_on_goals": True}


def test_given_up_co2_airing_closes_with_the_slow_fall_reason_and_claims_no_goal():
    result = evaluate_room(_running(co2_given_up=True), GOALS, False)
    assert result.action == "Close" and result.reason == CO2_SLOW_FALL_CLOSE_REASON
    assert result.close_kind == "air_no_longer_helps" and not result.goals_reached_now
    assert "ppm" in _close_reason(result, GOALS) and "erreicht" not in _close_reason(result, GOALS)


def test_the_give_up_closes_only_for_a_co2_only_airing_of_a_room_that_closes_on_goals():
    assert evaluate_room(_running(co2_given_up=True), GOALS, False).action == "Close"
    assert evaluate_room(_running(co2_lead_latched=True), GOALS, False).action != "Close"  # still held: no give-up yet
    assert evaluate_room(_running(co2_given_up=True, session_co2_only=False), GOALS, False).reason != CO2_SLOW_FALL_CLOSE_REASON
    keep_drying = {k: v for k, v in GOALS.items() if k != "room_close_on_goals"}  # the room chose to keep drying
    result = evaluate_room(_running(co2_given_up=True), keep_drying, False)
    assert result.reason != CO2_SLOW_FALL_CLOSE_REASON and result.action != "Close"


def test_mould_protection_keeps_the_airing_open_after_a_give_up():
    cold = dict(temperature=21.0, humidity=58.0, reference_temperature=-8.0, reference_humidity=80.0, surface_rh_helper=92.0)
    result = evaluate_room(_running(co2_given_up=True, **cold), GOALS, False)
    assert result.action == "Continue ventilating" and not result.close_recommended


def test_a_sensor_reporting_less_often_than_every_two_minutes_gives_no_slope():
    assert co2_slope_ppm_min([(0, 800), (300, 700), (600, 650)]) is None
    assert co2_airing_given_up(700, OPTIONS, None, 10.0, 0.0) is False  # so its airing keeps going


def _walk(series, options=OPTIONS, hold_s=CO2_GIVE_UP_HOLD_S):
    """First (seconds, ppm) at which the series is given up, steepest fall and hold time taken like the coordinator does."""
    steepest, since = 0.0, None
    for i, (t, ppm) in enumerate(series):
        slope = co2_slope_ppm_min([(float(s), float(p)) for s, p in series[: i + 1]])
        steepest = steepest if slope is None else min(steepest, slope)
        since, confirmed = co2_give_up_confirmed(since, float(t), co2_airing_given_up(float(ppm), options, slope, t / 60.0, steepest), hold_s)
        if confirmed:
            return t, ppm
    return None


def _decay(start, target, k, minutes=60, step_s=60):
    """CO2 relaxing exponentially toward ``target`` (exchange rate k per minute), one sample per ``step_s``."""
    return [(s, target + (start - target) * (1 - k) ** (s / 60)) for s in range(0, minutes * 60 + 1, step_s)]


def test_a_slow_steady_fall_is_never_given_up_while_it_still_reaches_the_release_level():
    open_window = [s for s in _decay(1000, 420, 0.04) if s[1] >= 600]
    assert _walk(open_window) is None  # k = 0.04: slope -23 at 990, -19 at 900, 600 reached in ~25 min
    assert _walk(_decay(1000, 420, 0.015)) is None  # tilted, 60 min


def _noisy_walk(seed, hold_s):
    """k = 0.04 toward 420, a report every 15 s with sensor noise (sigma 3 ppm); only while the true CO2 is still >= 600."""
    rng = random.Random(seed)
    series = [(t, round(ppm + rng.gauss(0, 3))) for t, ppm in _decay(1000, 420, 0.04, step_s=15) if ppm >= 600]
    return _walk(series, hold_s=hold_s)


def test_sensor_noise_does_not_end_a_slow_steady_fall_because_of_the_hold_time():
    assert _noisy_walk(SEED, CO2_GIVE_UP_HOLD_S) is None
    assert _noisy_walk(SEED, 0.0) is not None  # without the hold one noisy slope gives up: the hold matters


def test_a_plateau_with_slow_exchange_is_given_up_above_the_plateau():
    t, ppm = _walk(_decay(1000, 650, 0.05))
    assert 650 < ppm < 750, (t, ppm)


def test_issue_example_is_silent_while_falling_fast_and_gives_up_after_the_hold_time():
    assert _walk(ISSUE_SERIES) == (480, 683)  # the condition first holds at 360 s / 698 ppm
    assert _walk(ISSUE_SERIES, hold_s=0.0) == (360, 698)
    slopes = [co2_slope_ppm_min([(float(s), float(p)) for s, p in ISSUE_SERIES[: i + 1]]) for i in range(1, 7)]
    assert [None if s is None else round(s) for s in slopes] == [-170, -95, -38, -17, -8, None]  # 2-minute fit of sparse samples
