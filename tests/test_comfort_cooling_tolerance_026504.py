"""0.26.5.4 (community report): comfort cooling tolerates reference air at most ``close_delta`` wetter.

Bedroom 22.1 °C / 46 %, temperature goal 19 °C (manual), window tilted for a
long time, reference air 3.5 K cooler but 0.28 g/m³ wetter (about -2 ml in
5 minutes). Comfort cooling required zero moisture ingress, so the normal close
rule ("goal reached or extra benefit too small") closed the window although the
room was 3 K above its goal. A difference below ``close_delta`` is noise for
the close rule; comfort cooling now uses the same limit. Real moisture ingress
still closes (``tests/test_comfort_cooling_026503.py`` is unchanged).
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "operating_profile": "comfort", "min_duration_min": 5, "max_duration_min": 30,
           "cooling_min_outdoor_delta_c": 2.0, "cooling_max_indoor_rh": 70.0, "close_delta": 0.4}


def _rh_for(temp: float, ah: float) -> float:
    low, high = 0.0, 100.0
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if absolute_humidity(temp, mid) < ah else (low, mid)
    return (low + high) / 2


def _bedroom(*, temp=22.1, rh=46.0, ref_temp=18.6, ah_offset=0.28, **overrides) -> RoomInput:
    ref_ah = absolute_humidity(temp, rh) + ah_offset
    values = dict(
        key="schlafzimmer", name="Schlafzimmer", temperature=temp, humidity=rh, reference_temperature=ref_temp,
        reference_humidity=_rh_for(ref_temp, ref_ah), volume_m3=36, contact_open=True, contact_open_seconds=2 * 3600,
        session_active=True, session_elapsed_min=120, session_start_temp=23.0, learning_rate=0.04,
        session_fresh_measurements=8, comfort_target_c=19.0,
    )
    values.update(overrides)
    return RoomInput(**values)


def test_bedroom_keeps_cooling_despite_minimal_ingress() -> None:
    result = evaluate_room(_bedroom(), OPTIONS, False)
    assert -5 <= result.moisture_effect_next_5_min_ml < 0
    assert result.action == "Continue ventilating"
    assert result.close_recommended is False
    assert result.comfort_cooling_active is True


@pytest.mark.parametrize("offset", [0.0, -0.2])
def test_zero_and_drying_reference_keep_cooling(offset) -> None:
    result = evaluate_room(_bedroom(ah_offset=offset), OPTIONS, False)
    assert result.action == "Continue ventilating" and result.comfort_cooling_active is True


@pytest.mark.parametrize("offset", [0.5, 2.0, 6.0])
def test_noticeable_ingress_still_closes(offset) -> None:
    result = evaluate_room(_bedroom(ah_offset=offset), OPTIONS, False)
    assert result.action == "Close" and result.comfort_cooling_active is False


def test_close_delta_zero_restores_the_strict_rule() -> None:
    assert evaluate_room(_bedroom(), {**OPTIONS, "close_delta": 0.0}, False).action == "Close"


@pytest.mark.parametrize(("temp", "expected"), [(22.1, "Continue ventilating"), (19.6, "Continue ventilating"),
                                                 (19.5, "Continue ventilating"), (19.4, "Close")])
def test_goal_hysteresis_19_degrees(temp, expected) -> None:
    room = _bedroom(temp=temp, ref_temp=temp - 3.0, session_start_temp=temp + 0.2)
    assert evaluate_room(room, OPTIONS, False).action == expected


@pytest.mark.parametrize(("cooling_delta", "expected"), [(2.0, "Continue ventilating"), (1.9, "Close")])
def test_minimum_reference_temperature_difference(cooling_delta, expected) -> None:
    assert evaluate_room(_bedroom(ref_temp=22.1 - cooling_delta), OPTIONS, False).action == expected


def test_without_goal_disabled_cooling_or_humid_room_it_closes() -> None:
    assert evaluate_room(_bedroom(comfort_target_c=None), OPTIONS, False).action == "Close"
    assert evaluate_room(_bedroom(cooling_allowed=False), OPTIONS, False).action == "Close"
    assert evaluate_room(_bedroom(rh=72.0), OPTIONS, False).action == "Close"


def test_session_beyond_max_duration_and_old_behaviour_closes_without_cooling() -> None:
    long_run = _bedroom(session_elapsed_min=600, contact_open_seconds=600 * 60)
    assert evaluate_room(long_run, OPTIONS, False).action == "Continue ventilating"
    assert evaluate_room(_bedroom(session_elapsed_min=600, contact_open_seconds=600 * 60, comfort_target_c=None), OPTIONS, False).action == "Close"


def test_closed_window_is_not_asked_to_open_by_the_tolerance() -> None:
    closed = _bedroom(contact_open=False, contact_open_seconds=0, session_active=False, session_elapsed_min=0)
    assert evaluate_room(closed, OPTIONS, False).comfort_cooling_active is False
