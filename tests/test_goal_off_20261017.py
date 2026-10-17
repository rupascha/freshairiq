"""0.26.5.1 (owner request): a room goal can be switched off from priority 2 on.

A switched-off CO2 or temperature goal is no longer shown, never counts as an
open goal and starts or prolongs no airing of its own. Dehumidification cannot
be switched off; protection limits keep working.
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.goals import SWITCHABLE_GOALS, evaluate_goals, normalise_disabled_goals
from custom_components.freshairiq.model import RoomInput, evaluate_room


def _goals(**overrides):
    values = dict(
        humidity=70, target_rh=55, co2=1500, co2_warn=1000, temperature=26, temperature_target=21,
        priorities=["humidity", "co2", "temperature"], available_goals=["humidity", "co2", "temperature"],
    )
    values.update(overrides)
    return evaluate_goals(**values)


def test_only_co2_and_temperature_can_be_switched_off() -> None:
    assert SWITCHABLE_GOALS == ("co2", "temperature")
    assert normalise_disabled_goals(["temperature", "humidity", "bogus", "co2"]) == ["co2", "temperature"]
    assert normalise_disabled_goals(("co2",)) == ["co2"]
    assert normalise_disabled_goals("co2") == []
    assert normalise_disabled_goals(None) == []


def test_without_switched_off_goals_the_result_is_unchanged() -> None:
    state = _goals()
    assert "disabled_goals" not in state
    assert state["priorities"] == ["humidity", "co2", "temperature"]
    assert all(row["active"] and "disabled" not in row for row in state["goals"])


def test_switched_off_goals_are_inactive_and_never_open() -> None:
    state = _goals(disabled_goals=["co2", "temperature"], humidity=50)
    assert state["disabled_goals"] == ["co2", "temperature"]
    assert state["priorities"] == ["humidity"]
    rows = {row["id"]: row for row in state["goals"]}
    for goal in ("co2", "temperature"):
        assert rows[goal]["active"] is False and rows[goal]["disabled"] is True
        assert rows[goal]["reached"] is False and rows[goal]["eta_min"] is None
    # humidity (50 % <= 55 %) is reached, the high CO2 and temperature no longer count
    assert state["all_active_goals_reached"] is True and state["highest_open_goal"] is None


def test_humidity_stays_even_when_listed_as_switched_off() -> None:
    state = _goals(disabled_goals=["humidity", "temperature"])
    assert state["disabled_goals"] == ["temperature"]
    assert state["priorities"] == ["humidity", "co2"]
    assert state["highest_open_goal"] == "humidity"


def _cooling_room(**overrides) -> RoomInput:
    return RoomInput("living", "Living room", 25, 55, 20, 60, 80, False, 0, **overrides)


def test_switched_off_temperature_goal_starts_no_airing_for_cooling() -> None:
    options = {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}
    assert evaluate_room(_cooling_room(), options, False).cooling_candidate
    off = evaluate_room(_cooling_room(cooling_allowed=False), options, False)
    assert not off.cooling_candidate
    assert off.action != "Ventilate for cooling"


def test_switched_off_temperature_goal_does_not_prolong_a_cooling_session() -> None:
    options = {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling", "cooling_start_temp_c": 24, "cooling_min_outdoor_delta_c": 2}
    base = dict(
        key="living", name="Living room", temperature=25, humidity=50,
        reference_temperature=18, reference_humidity=55, volume_m3=80,
        contact_open=True, contact_open_seconds=600, session_active=True, session_elapsed_min=8,
        session_start_temp=27, learning_rate=0.04, session_fresh_measurements=2,
    )
    on = evaluate_room(RoomInput(**base), options, False)
    assert on.action == "Continue ventilating" and on.reason.startswith("Cooling remains useful")
    off = evaluate_room(RoomInput(**base, cooling_allowed=False), options, False)
    # the session may continue for moisture, but never because of cooling
    assert not off.reason.startswith("Cooling remains useful")
    assert not off.cooling_candidate
