"""0.26.5.3 hotfix (GitHub #19, community report): new cooling airings in the comfort profile.

Case A: room 24.3 °C, manual comfort target 25.5 °C – FreshAirIQ said "Zum Kühlen lüften".
Case B: room 24.0 °C, thermostat target 24.0 °C, outdoors 9.7 °C – the house said
"target reached, keep closed" while the room said "Zum Kühlen lüften".

A new cooling airing only looked at the house-wide ``cooling_start_temp_c``
(24 °C); the room's comfort target was ignored. Now, in the comfort profile, a
room with a temperature goal starts a new cooling airing only from its comfort
target plus the margin that already keeps a running one open. The house-wide
value stays the lower bound; the summer profile and rooms without a target are
unchanged; humidity, CO₂ and protection keep their priority.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import COMFORT_COOLING_MARGIN_C, RoomInput, _cooling_start_c, evaluate_room

COMFORT = {**DEFAULT_OPTIONS, "operating_profile": "comfort", "min_duration_min": 3, "max_duration_min": 30}
SUMMER = {**COMFORT, "operating_profile": "summer_cooling"}
DEHUMIDIFY = {**COMFORT, "operating_profile": "dehumidify"}


def _room(**overrides) -> RoomInput:
    values = dict(
        key="wohnzimmer", name="Wohnzimmer", temperature=24.3, humidity=50, reference_temperature=15.0,
        reference_humidity=75, volume_m3=50, contact_open=False, contact_open_seconds=0, learning_rate=0.03,
        comfort_target_c=25.5,
    )
    values.update(overrides)
    return RoomInput(**values)


def _running(**overrides) -> RoomInput:
    values = dict(contact_open=True, contact_open_seconds=1500, session_active=True, session_elapsed_min=25,
                  session_fresh_measurements=8)
    values.update(overrides)
    values.setdefault("session_start_temp", values.get("temperature", 24.3) + 0.4)
    return _room(**values)


def _cools(room: RoomInput, options=COMFORT) -> bool:
    result = evaluate_room(room, options, False)
    assert result.action != "Ventilate for cooling" or result.cooling_candidate
    return result.action == "Ventilate for cooling"


# --------------------------------------------------------------------------- the two reports
def test_case_a_manual_target_above_the_room_is_not_cooled() -> None:
    result = evaluate_room(_room(), COMFORT, False)
    assert result.action != "Ventilate for cooling" and result.cooling_candidate is False
    # the house-wide threshold alone used to decide: without a target the room still cools as before
    assert _cools(_room(comfort_target_c=None))


def test_case_b_thermostat_target_reached_is_not_cooled() -> None:
    room = _room(temperature=24.0, comfort_target_c=24.0, reference_temperature=9.7, reference_humidity=85)
    result = evaluate_room(room, COMFORT, False)
    assert result.action != "Ventilate for cooling" and result.cooling_candidate is False


# --------------------------------------------------------------------------- below / at / above the target
@pytest.mark.parametrize(("target", "temperature", "cools"), [
    (25.5, 24.3, False),   # below the target
    (25.5, 25.5, False),   # at the target
    (25.5, 25.9, False),   # inside the comfort margin
    (25.5, 26.0, True),    # target + margin: the same point that keeps a running airing open
    (25.5, 27.0, True),    # clearly above
    (24.0, 24.0, False),
    (24.0, 24.5, True),
    (22.0, 23.5, False),   # low target: the house-wide 24 °C stays the lower bound (no earlier prompts)
    (22.0, 24.0, True),
    (22.0, 24.5, True),
])
def test_start_follows_the_comfort_target(target, temperature, cools) -> None:
    assert _cools(_room(comfort_target_c=target, temperature=temperature)) is cools


def test_start_threshold_and_continuation_share_one_margin() -> None:
    assert _cooling_start_c(_room(comfort_target_c=25.5), COMFORT, "comfort") == 25.5 + COMFORT_COOLING_MARGIN_C
    assert _cooling_start_c(_room(comfort_target_c=21.0), COMFORT, "comfort") == 24.0
    assert _cooling_start_c(_room(comfort_target_c=None), COMFORT, "comfort") == 24.0
    assert _cooling_start_c(_room(comfort_target_c=25.5), SUMMER, "summer_cooling") == 24.0
    assert _cooling_start_c(_room(comfort_target_c=25.5), {**COMFORT, "cooling_start_temp_c": 27.0}, "comfort") == 27.0


def test_cooling_still_needs_cooler_outdoor_air_and_a_dry_enough_room() -> None:
    assert not _cools(_room(comfort_target_c=22.0, temperature=25.0, reference_temperature=24.0))
    assert not _cools(_room(comfort_target_c=22.0, temperature=25.0, humidity=75, reference_humidity=40, reference_temperature=12.0))


# --------------------------------------------------------------------------- profiles, goal switched off, no target
def test_summer_profile_is_unchanged() -> None:
    assert _cools(_room(), SUMMER)  # 24.3 °C ≥ 24 °C: summer cooling ignores the comfort target as before
    assert not _cools(_room(temperature=23.9), SUMMER)


def test_dehumidify_profile_never_starts_cooling() -> None:
    assert not _cools(_room(temperature=28.0, comfort_target_c=21.0), DEHUMIDIFY)
    assert not _cools(_room(temperature=28.0, comfort_target_c=None), DEHUMIDIFY)


@pytest.mark.parametrize("options", [COMFORT, SUMMER, DEHUMIDIFY])
def test_switched_off_temperature_goal_never_cools(options) -> None:
    assert not _cools(_room(temperature=28.0, comfort_target_c=None, cooling_allowed=False), options)


def test_room_without_target_keeps_the_house_wide_threshold() -> None:
    assert _cools(_room(comfort_target_c=None, temperature=24.0))
    assert not _cools(_room(comfort_target_c=None, temperature=23.9))


# --------------------------------------------------------------------------- humidity, CO₂ and protection keep priority
def test_humidity_and_co2_are_not_affected() -> None:
    humid = evaluate_room(_room(humidity=72), COMFORT, False)
    assert humid.action == "Ventilate" and humid.ventilation_candidate
    stale = evaluate_room(_room(co2=1600), COMFORT, False)
    assert stale.action == "Ventilate"
    for options in (COMFORT, SUMMER, DEHUMIDIFY):
        assert evaluate_room(_room(humidity=72), options, False).action == evaluate_room(_room(humidity=72, comfort_target_c=None), options, False).action


def test_protection_still_blocks_and_only_a_real_cooling_need_is_blocked() -> None:
    pollen = {**COMFORT, "pollen_enabled": True, "pollen_max": 4.0}
    assert evaluate_room(_room(comfort_target_c=22.0, temperature=25.0, pollen_index=5.0), pollen, False).action == "Do not ventilate"
    assert evaluate_room(_room(pollen_index=5.0), pollen, False).action != "Do not ventilate"  # no cooling need at 24.3 / 25.5


# --------------------------------------------------------------------------- running airings
def test_a_running_airing_above_the_target_keeps_cooling() -> None:
    result = evaluate_room(_running(comfort_target_c=24.0, temperature=25.0), COMFORT, False)
    assert result.action == "Continue ventilating" and result.reason.startswith("Cooling remains useful")
    assert result.comfort_cooling_active


def test_a_running_airing_at_the_target_is_not_kept_open_for_cooling() -> None:
    result = evaluate_room(_running(comfort_target_c=25.5), COMFORT, False)
    assert not result.comfort_cooling_active and not result.reason.startswith("Cooling remains useful")
    case_b = evaluate_room(_running(temperature=24.0, comfort_target_c=24.0, reference_temperature=9.7, reference_humidity=85), COMFORT, False)
    assert not case_b.comfort_cooling_active and case_b.action == "Close"
