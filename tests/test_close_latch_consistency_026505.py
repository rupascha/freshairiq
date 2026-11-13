"""0.26.5.5 (community diagnosis 28.10.): a close must not depend on FreshAirIQ's own last answer.

Laundry room, 11:46–12:01: 85 changes "Close" ↔ "Continue ventilating" every ~10 s with
unchanged readings. The plateau rule closed the airing; the stored close was then
released because the forecast still promised a large return, the next cycle closed
again – forever. Bedroom: a stored close held "Close" although the same readings
without it said "Continue ventilating" for comfort cooling.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 30}


def _laundry(**changes) -> RoomInput:
    room = RoomInput(
        key="waschkueche", name="Waschküche", temperature=24.0, humidity=54.0, reference_temperature=12.0,
        reference_humidity=20.0, volume_m3=9.0, contact_open=True, contact_open_seconds=900.0, learning_rate=0.03,
        session_active=True, session_elapsed_min=20.0, session_fresh_measurements=4, humidity_plateau=True,
    )
    return replace(room, **changes)


def _bedroom(**changes) -> RoomInput:
    room = RoomInput(
        key="schlafzimmer", name="Schlafzimmer", temperature=21.7, humidity=51.0, reference_temperature=12.0,
        reference_humidity=80.0, volume_m3=36.0, contact_open=True, contact_open_seconds=1900.0, learning_rate=0.03,
        session_active=True, session_elapsed_min=31.0, session_fresh_measurements=4, comfort_target_c=19.0,
    )
    return replace(room, **changes)


def _run(room: RoomInput, cycles: int = 40, options=OPTIONS) -> list[str]:
    """Feed every answer back like the coordinator does (``close_notified``)."""
    actions, notified = [], room.close_notified
    for _ in range(cycles):
        result = evaluate_room(replace(room, close_notified=notified), options, False)
        actions.append(result.action)
        notified = result.close_recommended
    return actions


@pytest.mark.parametrize("notified", [False, True])
def test_plateau_close_with_a_large_forecast_stays_closed(notified) -> None:
    # Testvermerk 0.26.7.0 (F11, owner decision): a plateau no longer closes while the reference air is clearly drier
    # (here 2 g/m³ outside against 12 g/m³ inside). The point of this test stays: the answer never alternates.
    room = _laundry(close_notified=notified)
    assert evaluate_room(room, OPTIONS, False).next_5_min_ml >= 10  # forecast still promises a lot …
    actions = _run(room)
    assert set(actions) == {"Continue ventilating"}  # … and every cycle answers the same
    # once the reference air no longer dries the room, the same plateau closes – again without alternating
    exhausted = _laundry(close_notified=notified, reference_temperature=24.0, reference_humidity=53.0)
    assert set(_run(exhausted)) == {"Close"}


def test_identical_readings_never_alternate() -> None:
    for room in (_laundry(), _laundry(humidity_plateau=False), _laundry(moisture_source_active=True),
                 _laundry(co2=1500.0), _laundry(session_elapsed_min=2.0), _laundry(session_elapsed_min=29.0),
                 _bedroom(), _bedroom(comfort_target_c=None), _bedroom(cooling_allowed=False)):
        actions = _run(room, 35)
        assert len(set(actions[2:])) == 1, (room.key, actions)


def test_plateau_ends_moisture_comes_in_and_sources_keep_their_rules() -> None:
    assert set(_run(_laundry(humidity_plateau=False))) == {"Continue ventilating"}  # still drying, no plateau
    assert set(_run(_laundry(moisture_source_active=True))) == {"Continue ventilating"}  # a source keeps it open
    wet = _laundry(humidity_plateau=False, reference_temperature=24.0, reference_humidity=80.0)
    assert set(_run(wet)) == {"Close"}  # moisture would come in


def test_comfort_cooling_releases_a_stored_close() -> None:
    fresh = evaluate_room(_bedroom(close_notified=False), OPTIONS, False)
    assert fresh.action == "Continue ventilating" and fresh.comfort_cooling_active
    latched = evaluate_room(_bedroom(close_notified=True), OPTIONS, False)
    assert latched.action == "Continue ventilating"  # the stored close no longer overrides the same readings


# Testvermerk 0.26.7.0 (F11): with clearly drier reference air a stored close is lifted again once confirmed, fresh
# readings prove the drying (owner: "Schließmeldung vorher gespeichert, Entfeuchtung wird erneut nachgewiesen").
# The cases without a temperature goal therefore run with reference air that no longer dries the room.
_EXHAUSTED = {"reference_temperature": 21.7, "reference_humidity": 50.0}


@pytest.mark.parametrize("change", [
    {"comfort_target_c": None, **_EXHAUSTED},   # no temperature goal
    {"cooling_allowed": False, **_EXHAUSTED},   # temperature goal switched off
    {"reference_temperature": 20.5},            # reference air not clearly cooler
    {"reference_humidity": 99.0, "reference_temperature": 19.5},  # noteworthy moisture would come in
    {"session_fresh_measurements": 1},          # readings not confirmed yet
    {"measurements_stale": True},               # readings too old to trust
])
def test_a_stored_close_stays_without_a_proven_cooling_reason(change) -> None:
    assert evaluate_room(_bedroom(close_notified=True, **change), OPTIONS, False).action == "Close"


@pytest.mark.parametrize("change", [{"comfort_target_c": None}, {"cooling_allowed": False}])
def test_f11_a_stored_close_is_lifted_when_confirmed_readings_prove_drying_again(change) -> None:
    """0.26.7.0 (F11): drier air again (1.2 g/m³), confirmed and fresh readings – the stored close is lifted, without alternating."""
    room = _bedroom(close_notified=True, **change)
    assert evaluate_room(room, OPTIONS, False).action == "Continue ventilating"
    assert set(_run(room)[1:]) == {"Continue ventilating"}
    # unconfirmed or stale readings never lift it
    assert evaluate_room(replace(room, session_fresh_measurements=1), OPTIONS, False).action == "Close"
    assert evaluate_room(replace(room, measurements_stale=True), OPTIONS, False).action == "Close"
