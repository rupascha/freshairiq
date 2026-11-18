"""K02 (0.26.7.1): the real coordinator applies a room's chosen close strategy; other rooms are unchanged.

Bath 23.4 °C, outdoor 9 °C / 82 % (clearly drier). With "close once the goals are reached" the bath is asked to close
once its humidity is at or below ``target_rh`` on fresh readings – since IQ2 (0.26.7.1) that is the default; a room
that chose "keep_drying" keeps airing while the air dries.
"""
from __future__ import annotations

from custom_components.freshairiq.room_close_strategy import CONF_ROOM_CLOSE_STRATEGY
from ha_tests.test_cov_coordinator_b import HUM, OPTIONS, _cleanup_coordinators, _data, _make, _rooms, _with  # noqa: F401


async def _airing(hass, freezer, strategy: str | None):
    rooms = _rooms() if strategy is None else _with(_rooms(), "bad", **{CONF_ROOM_CLOSE_STRATEGY: strategy})
    d = await _make(hass, freezer, data=_data(rooms), options={**OPTIONS, "target_rh": 58.0, "min_duration_min": 3})
    for _ in range(2):
        await d.step(60)
    await d.step(60, binary_sensor__bad_fenster="on")
    seen = []
    for rh in (75.0, 70.0, 65.0, 61.0, 58.5, 57.5, 56.5, 56.0):
        await d.step(60, sensor__bad_h=(rh, HUM))
        room = d.room("bad")
        seen.append((rh, room["action"], room["close_recommended"]))
    return d, seen


async def test_goal_strategy_closes_once_the_humidity_goal_is_reached(hass, freezer) -> None:
    d, seen = await _airing(hass, freezer, "goals_reached")
    assert all(not close for rh, _action, close in seen if rh > 58.0), seen      # never before the goal
    assert any(close for rh, _action, close in seen if rh <= 58.0), seen
    last = d.room("bad")
    assert last["close_recommended"] and "goals" in str(last["reason"]).lower() + " ".join(last.get("recommendation_reasons") or []).lower()


async def test_keep_drying_room_keeps_airing_while_the_air_still_dries(hass, freezer) -> None:
    # Testvermerk 0.26.7.1 (IQ2, owner decision of 15.11.2026): this was the default; the F11 behaviour it protects
    # is now the explicit room choice "keep_drying".
    _d, seen = await _airing(hass, freezer, "keep_drying")
    assert all(not close for _rh, _action, close in seen), seen


async def test_default_room_closes_once_the_humidity_goal_is_reached(hass, freezer) -> None:
    """IQ2 default (nothing chosen): the same behaviour as the explicit goal strategy – also for a stored former default."""
    for stored in (None, "continue_while_drying"):
        d, seen = await _airing(hass, freezer, stored)
        assert all(not close for rh, _action, close in seen if rh > 58.0), (stored, seen)
        assert all(close and action == "Close" for rh, action, close in seen if rh <= 58.0), (stored, seen)
        assert d.room("bad")["close_kind"] in {"goals_reached", "goals_held"}
