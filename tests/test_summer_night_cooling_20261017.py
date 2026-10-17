"""0.26.5.1 (community feedback): night cooling in the "summer cooling" profile.

An airing that still cools (room warm, outdoor air clearly cooler) is no longer
ended by the maximum airing duration. It is ended explicitly once the outdoor
air is no longer cooler than the warm room, so the collected coolness stays
inside. Other profiles and switched-off temperature goals keep the old rules.
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import (
    SUMMER_WARMING_CLOSE_REASON,
    SUMMER_WARMING_MARGIN_C,
    RoomInput,
    evaluate_room,
)

SUMMER = {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling", "cooling_start_temp_c": 24,
          "cooling_min_outdoor_delta_c": 2, "max_duration_min": 20}


def _room(**overrides) -> RoomInput:
    values = dict(
        key="schlaf", name="Schlafzimmer", temperature=26.0, humidity=50.0,
        reference_temperature=18.0, reference_humidity=60.0, volume_m3=40.0,
        contact_open=True, contact_open_seconds=3600, session_active=True, session_elapsed_min=60,
        session_start_temp=28.0, learning_rate=0.04, session_fresh_measurements=2,
    )
    values.update(overrides)
    return RoomInput(**values)


def test_cooling_airing_is_not_ended_by_the_maximum_duration() -> None:
    result = evaluate_room(_room(), SUMMER, False)
    assert result.action == "Continue ventilating"
    assert result.reason.startswith("Cooling remains useful")
    # a close latched earlier (e.g. by the maximum duration) is released again
    latched = evaluate_room(_room(close_notified=True), SUMMER, False)
    assert latched.action == "Continue ventilating"


def test_other_profiles_keep_the_maximum_duration() -> None:
    options = {**SUMMER, "operating_profile": "balanced"}
    assert evaluate_room(_room(), options, False).action == "Close"


def test_closes_when_outdoor_air_is_no_longer_cooler() -> None:
    for outdoor in (26.0 - SUMMER_WARMING_MARGIN_C, 26.0, 29.0):
        result = evaluate_room(_room(reference_temperature=outdoor, session_elapsed_min=5), SUMMER, False)
        assert result.action == "Close", outdoor
        assert result.reason == SUMMER_WARMING_CLOSE_REASON
    # still slightly cooler outside: no warming close yet (short session, nothing reached)
    cooler = evaluate_room(_room(reference_temperature=25.0, session_elapsed_min=5), SUMMER, False)
    assert cooler.reason != SUMMER_WARMING_CLOSE_REASON


def test_warming_keeps_the_close_latched() -> None:
    result = evaluate_room(_room(reference_temperature=27.0, close_notified=True, session_elapsed_min=5), SUMMER, False)
    assert result.action == "Close" and result.reason == SUMMER_WARMING_CLOSE_REASON


def test_no_warming_close_for_a_cool_room_or_switched_off_goal() -> None:
    # room already below the cooling range: outdoor air at room level is not "warming"
    cool = evaluate_room(_room(temperature=21.0, reference_temperature=21.0, session_elapsed_min=5), SUMMER, False)
    assert cool.reason != SUMMER_WARMING_CLOSE_REASON
    off = evaluate_room(_room(reference_temperature=27.0, session_elapsed_min=5, cooling_allowed=False), SUMMER, False)
    assert off.reason != SUMMER_WARMING_CLOSE_REASON
    # the switched-off temperature goal also brings back the maximum duration
    assert evaluate_room(_room(cooling_allowed=False), SUMMER, False).action == "Close"


def test_fan_only_and_urgent_rooms_are_not_closed_for_warming() -> None:
    fan = evaluate_room(_room(reference_temperature=27.0, session_elapsed_min=5, mechanical_only=True), SUMMER, False)
    assert fan.reason != SUMMER_WARMING_CLOSE_REASON
    stale = evaluate_room(_room(reference_temperature=27.0, session_elapsed_min=5, co2=3000), SUMMER, False)
    assert stale.reason != SUMMER_WARMING_CLOSE_REASON
