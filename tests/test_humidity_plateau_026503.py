"""0.26.5.3 (community, heinzel): bathroom fan stuck at 59 % with target 58 %.

FreshAirIQ showed "noch 3 Minuten" for over half an hour and never said
"switch off the fan": the supply air only allowed ~58.7 %, the countdown was
distance ÷ current rate (both shrink alike near the equilibrium), and a fan
only stopped when moisture came in. Now the target is recognised as not
reachable with this air, and a sliding 15-minute plateau ends the airing.
"""
from __future__ import annotations

from math import exp

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.goals import evaluate_goals
from custom_components.freshairiq.humidity_plateau import (
    PLATEAU_WINDOW_MIN,
    equilibrium_rh,
    goal_unreachable,
    humidity_eta,
    humidity_plateau,
    record_sample,
    track_session,
)
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 30}


def test_equilibrium_from_the_supply_air() -> None:
    ah = absolute_humidity(21.0, 58.7)
    assert round(equilibrium_rh(21.0, ah), 1) == 58.7
    assert equilibrium_rh(None, ah) is None and equilibrium_rh(21.0, 0) is None and equilibrium_rh(80.0, ah) is None
    assert equilibrium_rh(float("nan"), ah) is None


def test_the_countdown_is_honest() -> None:
    # unreachable: the air allows only 58.7 % – no countdown at all
    assert goal_unreachable(59.0, 58.0, 58.7) and humidity_eta(59.0, 58.0, -0.1, 58.7) is None
    # reachable: exponential approach, never shorter than the linear guess
    eta = humidity_eta(65.0, 58.0, -0.5, 50.0)
    assert eta is not None and eta > (65.0 - 58.0) / 0.5
    assert humidity_eta(57.0, 58.0, -0.5, 50.0) == 0.0
    assert humidity_eta(65.0, 58.0, None, 50.0) is None and humidity_eta(65.0, 58.0, 0.2, 50.0) is None
    assert humidity_eta(65.0, 58.0, -0.5, None) == 14.0  # closed room: linear as before
    assert humidity_eta(57.5, 58.0, -0.5, 57.0) == 0.0 and humidity_eta(59.0, 58.0, -0.5, 59.5) is None
    goals = evaluate_goals(humidity=59.0, target_rh=58.0, co2=None, co2_warn=1000, temperature=21, temperature_target=None,
                           humidity_rate_pct_min=-0.1, humidity_floor_rh=58.7)
    humidity = next(g for g in goals["goals"] if g["id"] == "humidity")
    assert humidity["unreachable"] is True and humidity["eta_min"] is None and humidity["floor_rh"] == 58.7


def test_the_sliding_window() -> None:
    window: list = []
    for minute in range(0, 20):
        window = record_sample(window, float(minute), 70.0 - minute * 0.5, 10.0 - minute * 0.08)
    assert not humidity_plateau(window, 19.0, 60.5, 8.48)  # still falling
    window = record_sample(window, 19.5, 60.0, 8.4)  # less than a minute later: not added
    assert len(window) == 20
    flat = []
    for minute in range(0, 20):
        flat = record_sample(flat, float(minute), 59.0, 9.0)
    assert humidity_plateau(flat, 19.0, 59.0, 9.0)
    assert not humidity_plateau(flat[-10:], 19.0, 59.0, 9.0)  # window not yet 15 minutes long
    assert record_sample(flat, 2.0, 59.0, 9.0) == [{"t": 2.0, "rh": 59.0, "ah": 9.0}]  # new airing
    assert len(record_sample([{"t": 0.0, "rh": 1, "ah": 1}] * 2 + ["x"], 45.0, 59.0, 9.0)) == 1  # older than 30 min pruned
    mem = {"session_humidity_window": flat}
    assert track_session(mem, session_active=False, elapsed_min=20.0, temp_c=21, rh=59) is False and "session_humidity_window" not in mem
    assert track_session({}, session_active=True, elapsed_min=1.0, temp_c="x", rh=59) is False


def _fan(**extra) -> RoomInput:
    # the anteroom air (50 %) is clearly drier – the room still stalls at ~59 %
    # (moisture coming from walls and towels, limited fan capacity)
    values = dict(key="bad", name="Bad", temperature=21.0, humidity=59.0, reference_temperature=21.0,
                  reference_humidity=50.0, volume_m3=20.0, contact_open=True, contact_open_seconds=2400,
                  session_active=True, session_elapsed_min=40.0, session_start_temp=21.0, learning_rate=0.03,
                  session_fresh_measurements=8, mechanical_only=True)
    values.update(extra)
    return RoomInput(**values)


def test_heinzels_fan_is_switched_off_once_the_humidity_stops_falling() -> None:
    """Humidity stalls near 58.7 % although the supply air is drier."""
    mem: dict = {}
    actions = []
    for minute in range(0, 61):
        rh = 58.7 + 9.3 * exp(-minute / 6.0)  # from 68 % towards 58.7 %
        plateau = track_session(mem, session_active=True, elapsed_min=float(minute), temp_c=21.0, rh=rh)
        actions.append(evaluate_room(_fan(humidity=rh, session_elapsed_min=float(minute), humidity_plateau=plateau), OPTIONS, False).action)
    first_off = actions.index("Close")
    assert actions[:20] == ["Continue ventilating"] * 20  # really drying at the start
    assert 20 <= first_off <= 45  # soon after the curve flattened – not "forever"


def test_what_keeps_the_fan_running() -> None:
    assert evaluate_room(_fan(), OPTIONS, False).action == "Continue ventilating"  # no plateau seen yet
    for extra in ({"moisture_source_active": True}, {"moisture_source_recovery": True}, {"co2": 1200.0}):
        assert evaluate_room(_fan(humidity_plateau=True, **extra), OPTIONS, False).action != "Close"
    assert evaluate_room(_fan(humidity_plateau=True), OPTIONS, False).action == "Close"


def test_a_window_inside_its_planned_time_also_ends_on_a_plateau() -> None:
    window = dict(mechanical_only=False, session_elapsed_min=12.0, session_target_min=25.0, reference_humidity=40.0,
                  reference_temperature=15.0, humidity=59.0)
    assert evaluate_room(_fan(**window), OPTIONS, False).action == "Continue ventilating"
    assert evaluate_room(_fan(humidity_plateau=True, **window), OPTIONS, False).action == "Close"
