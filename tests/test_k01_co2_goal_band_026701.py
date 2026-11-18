"""K01 (0.26.7.1): the CO2 goal follows the same entry/exit band as ``model.co2_lead``.

Before, a started CO2 airing (latched, kept open down to ``co2_release_ppm``) published the CO2 goal with target =
warning threshold and reached = True as soon as CO2 fell below it – while the room still said "keep airing for
CO2". Entry stays the warning threshold, exit stays the release level; both are taken from the existing helpers.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.goals import evaluate_goals
from custom_components.freshairiq.model import co2_lead, co2_release_ppm

WARN = 1000.0


def _co2(co2, *, options, latched, humidity=None, rate=None, disabled=None):
    state = evaluate_goals(humidity=humidity, target_rh=55.0, co2=co2, co2_warn=options.get("co2_warn", WARN),
                           temperature=None, temperature_target=None, co2_rate_ppm_min=rate,
                           co2_release=co2_release_ppm(options), co2_latched=latched, disabled_goals=disabled)
    return state, next(g for g in state["goals"] if g["id"] == "co2")


@pytest.mark.parametrize("release", [0, 750])  # derived (warn - 50) and configured
@pytest.mark.parametrize("co2", [700, 749, 750, 751, 900, 949, 950, 951, 999, 1000, 1001, 1400])
@pytest.mark.parametrize("latched", [False, True])
def test_goal_reached_is_exactly_the_negation_of_co2_lead(co2, latched, release):
    options = {"co2_warn": WARN, "co2_release": release}
    lead = co2_lead(co2, options, latched)
    _state, goal = _co2(co2, options=options, latched=latched)
    assert goal["reached"] is (not lead)
    assert goal["warn_ppm"] == WARN and goal["release_ppm"] == co2_release_ppm(options)
    # the published target is the level the room is actually working towards
    assert goal["target"] == (co2_release_ppm(options) if lead and latched else WARN)


def test_owner_case_warn_1000_release_750_current_900_latched():
    options = {"co2_warn": 1000, "co2_release": 750}
    assert co2_lead(900, options, True) is True
    state, goal = _co2(900, options=options, latched=True, rate=-10.0)
    assert goal["reached"] is False and goal["target"] == 750.0 and goal["latched"] is True
    assert goal["eta_min"] == 15.0  # (900 - 750) / 10 ppm/min, never 0 while the band is still open
    assert state["all_active_goals_reached"] is False and state["highest_open_goal"] == "co2"


def test_unlatched_below_warning_is_reached_and_shows_the_warning_threshold():
    _state, goal = _co2(900, options={"co2_warn": 1000, "co2_release": 750}, latched=False)
    assert goal["reached"] is True and goal["target"] == 1000.0 and goal["eta_min"] == 0.0 and goal["latched"] is False


def test_latch_ends_below_release_and_the_goal_is_reached():
    _state, goal = _co2(749, options={"co2_warn": 1000, "co2_release": 750}, latched=True)
    assert goal["reached"] is True and goal["latched"] is False and goal["target"] == 1000.0


def test_unknown_rate_never_invents_an_eta_inside_the_band():
    _state, goal = _co2(900, options={"co2_warn": 1000, "co2_release": 750}, latched=True, rate=None)
    assert goal["reached"] is False and goal["eta_min"] is None
    _state, goal = _co2(900, options={"co2_warn": 1000, "co2_release": 750}, latched=True, rate=+3.0)
    assert goal["eta_min"] is None


@pytest.mark.parametrize("bad", [None, "x", float("nan"), -5, 0, 1000, 1500])
def test_invalid_release_falls_back_to_the_warning_threshold_only(bad):
    # evaluate_goals never trusts a release level outside (0, warn): then the plain warning threshold applies
    state = evaluate_goals(humidity=None, target_rh=55, co2=990, co2_warn=1000, temperature=None, temperature_target=None,
                           co2_release=bad, co2_latched=True)
    goal = next(g for g in state["goals"] if g["id"] == "co2")
    assert goal["release_ppm"] is None and goal["target"] == 1000.0 and goal["reached"] is True


@pytest.mark.parametrize("bad", ["x", float("nan"), -5, 1500])
def test_invalid_release_options_resolve_like_co2_lead(bad):
    options = {"co2_warn": 1000, "co2_release": bad}
    _state, goal = _co2(980, options=options, latched=True)
    assert goal["reached"] is (not co2_lead(980, options, True))


def test_missing_sensor_keeps_the_goal_inactive_even_when_latched():
    state, goal = _co2(None, options={"co2_warn": 1000, "co2_release": 750}, latched=True)
    assert goal["active"] is False and goal["reached"] is False and goal["latched"] is False
    assert state["all_active_goals_reached"] is True


def test_disabled_co2_goal_stays_off_even_inside_the_band():
    _state, goal = _co2(900, options={"co2_warn": 1000, "co2_release": 750}, latched=True, disabled=["co2"])
    assert goal["active"] is False and goal.get("disabled") is True


def test_co2_together_with_humidity_keeps_both_goals_independent():
    state, goal = _co2(900, options={"co2_warn": 1000, "co2_release": 750}, latched=True, humidity=50.0)
    humidity = next(g for g in state["goals"] if g["id"] == "humidity")
    assert humidity["reached"] is True and goal["reached"] is False
    assert state["all_active_goals_reached"] is False


def test_no_flapping_across_a_falling_and_jittering_trace():
    options = {"co2_warn": 1000, "co2_release": 750}
    latched, seen = False, []
    for co2 in (980, 1005, 990, 999, 960, 1001, 900, 820, 760, 751, 755, 749, 752, 760, 990, 1000):
        latched = co2_lead(co2, options, latched)       # what the coordinator stores before the goals are built
        _state, goal = _co2(co2, options=options, latched=latched)
        seen.append(goal["reached"])
        assert goal["reached"] is (not latched)
    # open from the first 1005 ppm until it fell below 750, then reached and stays so below 1000 ppm
    assert seen == [True, False, False, False, False, False, False, False, False, False, False, True, True, True, True, False]


def test_restart_keeps_the_band_because_the_latch_is_persisted_room_memory():
    # mem["co2_lead_latched"] is part of the stored room memory; after a restart the same value is passed in
    options = {"co2_warn": 1000, "co2_release": 750}
    before = _co2(880, options=options, latched=True)[1]
    after_restart = _co2(880, options=options, latched=True)[1]
    assert before == after_restart and after_restart["reached"] is False
    # a restart without the stored latch (fresh install) starts at the warning threshold – never a guessed band
    assert _co2(880, options=options, latched=False)[1]["reached"] is True
