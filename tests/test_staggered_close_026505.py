"""0.26.5.5 (F04, GitHub #23): a floor/house close waits for the youngest window's own minimum time.

Bedroom open 5.1 min, bathroom 3.7 min, minimum airing time 5 min: the floor advice asked
both to close because the older room's own close (``hard_close``) or every room's "Close"
returned before the minimum-duration check. Real protection – moisture coming in – still
closes at once, with its own reason.
"""
from __future__ import annotations

from custom_components.freshairiq.consolidation import aggregate_close_allowed


def _room(key, elapsed, *, action="Continue ventilating", hard=False, delta=1.5):
    return {"key": key, "active": True, "close_decision_ready": True, "session_elapsed_min": elapsed, "action": action,
            "delta_g_m3": delta, "goal_state": {"hard_close": hard}}


def _allowed(rooms, **kw):
    return aggregate_close_allowed(rooms, low_return=kw.pop("low_return", True), thermal_bad=kw.pop("thermal_bad", False),
                                   min_duration_min=5, target_min=None, net_next5_ml=kw.pop("net", 20.0), close_delta=0.4, **kw)


def test_older_rooms_own_close_does_not_close_the_younger_window() -> None:
    assert _allowed([_room("schlaf", 5.2, action="Close", hard=True), _room("bad", 3.3)]) is False
    assert _allowed([_room("schlaf", 5.1, action="Close"), _room("bad", 3.7, action="Close")]) is False
    assert _allowed([_room("schlaf", 5.1), _room("bad", 3.7)], thermal_bad=True) is False


def test_once_every_window_had_its_minimum_time_the_floor_closes() -> None:
    assert _allowed([_room("schlaf", 6.0, action="Close", hard=True), _room("bad", 5.0)]) is True
    assert _allowed([_room("schlaf", 7.0, action="Close"), _room("bad", 5.5, action="Close")]) is True


def test_real_protection_still_closes_at_once() -> None:
    # moisture coming into the young room itself, or no net drying of the floor
    assert _allowed([_room("schlaf", 5.2, action="Close", hard=True), _room("bad", 3.3, delta=-0.6)]) is True
    assert _allowed([_room("schlaf", 5.2, action="Close", hard=True), _room("bad", 3.3)], net=-4.0) is True
    # the young room released its own close (its gate passed) – it is no longer protected
    assert _allowed([_room("schlaf", 5.2, action="Close", hard=True), _room("bad", 3.3, action="Close", hard=True)]) is True


def test_without_minimum_time_or_unknown_age_nothing_changes() -> None:
    rooms = [_room("schlaf", 5.2, action="Close", hard=True), _room("bad", None)]
    assert _allowed(rooms) is True
    assert aggregate_close_allowed([_room("schlaf", 5.2, action="Close", hard=True), _room("bad", 1.0)], low_return=True,
                                   thermal_bad=False, min_duration_min=None) is True


def test_planned_airing_time_still_holds_once_every_window_had_its_minimum() -> None:
    rooms = [_room("schlaf", 4.0, action="Close"), _room("bad", 3.5, action="Close")]
    assert aggregate_close_allowed(rooms, low_return=True, thermal_bad=False, min_duration_min=3, target_min=9, net_next5_ml=50.0) is False
