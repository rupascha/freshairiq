"""0.26.5.1 (owner request): optional automatic control of covers and exhaust fans.

* Per opening: the cover opens fully when the window/door opens and returns to
  its previous position when it is closed again (unless someone moved it).
* A cover of a passage door never closes while that door is not closed; a close
  started by anyone is stopped and the cover is opened again (in rooms where
  FreshAirIQ controls covers).
* Per room: covers close against the sun (summer cooling) and open again once
  the sun has left their window; exhaust fan after a moisture source or
  following the recommendation, with follow-up time and maximum runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.actuator_control import (
    COVER_CLOSE,
    COVER_OPEN,
    COVER_POSITION,
    COVER_STOP,
    FAN_CONTROL_MOISTURE_SOURCE,
    FAN_CONTROL_OFF,
    FAN_CONTROL_RECOMMENDATION,
    CoverSetup,
    CoverView,
    cover_setups,
    decide_cover,
    decide_fan,
    fan_demand,
    room_controls_covers,
)

WINDOW, DOOR = "binary_sensor.window", "sensor.balcony_door"
OPEN = [(COVER_OPEN, None)]
CLOSE = [(COVER_CLOSE, None)]


def _cover(view, setup, modes, *, mem, sun_auto=False, sun=False):
    return decide_cover(view=view, setup=setup, contact_modes=modes, sun_auto=sun_auto, sun_wants_close=sun, mem=mem)


def test_cover_setups_and_room_switch() -> None:
    room = {
        "contact_covers": {WINDOW: ["cover.a", "light.x"], DOOR: "cover.b", "binary_sensor.other": ["cover.a"]},
        "contact_cover_follow": {WINDOW: True},
        "contact_passage_doors": {DOOR: True},
    }
    setups = cover_setups(room)
    assert setups["cover.a"] == CoverSetup([WINDOW, "binary_sensor.other"], [WINDOW], [])
    assert setups["cover.b"] == CoverSetup([DOOR], [], [DOOR])
    assert cover_setups({"contact_covers": ["cover.a"]}) == {}
    assert room_controls_covers(room) is True
    assert room_controls_covers({"auto_sun_protection": True}) is True
    assert room_controls_covers({"contact_cover_follow": {WINDOW: False}}) is False
    assert room_controls_covers({"contact_cover_follow": "x"}) is False


def test_cover_view() -> None:
    assert CoverView("open", 100).fully_open and not CoverView("open", 40).fully_open
    assert CoverView("closed", 0).closed and CoverView("closed").closed and CoverView("open").fully_open
    inverted = CoverView("open", 0, zero_means_open=True)
    assert inverted.fully_open and inverted.open_position == 0 and inverted.closed_position == 100
    assert not CoverView("unavailable").available and CoverView("opening").available


def test_window_opens_the_cover_and_restores_the_previous_position() -> None:
    setup, mem = CoverSetup([WINDOW], [WINDOW], []), {}
    half = CoverView("open", 30, supports_position=True)
    assert _cover(half, setup, {WINDOW: "tilted"}, mem=mem) == OPEN
    assert mem == {"follow_active": True, "restore_position": 30, "restore_closed": False}
    # still open / already opening: nothing more
    assert _cover(CoverView("opening", 60, supports_position=True), setup, {WINDOW: "open"}, mem=mem) == []
    # unknown contact: keep waiting
    assert _cover(CoverView("open", 100, supports_position=True), setup, {WINDOW: "unknown"}, mem=mem) == []
    assert _cover(CoverView("open", 100, supports_position=True), setup, {WINDOW: "closed"}, mem=mem) == [(COVER_POSITION, 30)]
    assert mem == {"follow_active": False}


def test_restore_variants() -> None:
    setup = CoverSetup([WINDOW], [WINDOW], [])
    # closed cover without position: opened, then closed again
    mem: dict = {}
    assert _cover(CoverView("closed"), setup, {WINDOW: "open"}, mem=mem) == OPEN
    assert _cover(CoverView("open"), setup, {WINDOW: "closed"}, mem=mem) == CLOSE
    # already fully open: nothing to do either way
    mem = {}
    assert _cover(CoverView("open", 100), setup, {WINDOW: "open"}, mem=mem) == []
    assert _cover(CoverView("open", 100), setup, {WINDOW: "closed"}, mem=mem) == []
    # position known but not settable: closed is restored by closing, a middle position is left
    mem = {}
    _cover(CoverView("closed", 0), setup, {WINDOW: "open"}, mem=mem)
    assert _cover(CoverView("open", 100), setup, {WINDOW: "closed"}, mem=mem) == CLOSE
    mem = {}
    _cover(CoverView("open", 50), setup, {WINDOW: "open"}, mem=mem)
    assert _cover(CoverView("open", 100), setup, {WINDOW: "closed"}, mem=mem) == []
    # window closed again while the cover is still on its way up: restored as well
    mem = {}
    _cover(CoverView("closed", 0, supports_position=True), setup, {WINDOW: "open"}, mem=mem)
    assert _cover(CoverView("opening", 40, supports_position=True), setup, {WINDOW: "closed"}, mem=mem) == [(COVER_POSITION, 0)]


def test_a_cover_moved_by_someone_is_left_alone() -> None:
    setup, mem = CoverSetup([WINDOW], [WINDOW], []), {}
    _cover(CoverView("closed", 0, supports_position=True), setup, {WINDOW: "open"}, mem=mem)
    assert _cover(CoverView("open", 70, supports_position=True), setup, {WINDOW: "closed"}, mem=mem) == []
    # with sun protection waiting, the moved cover is not closed afterwards either
    mem = {}
    _cover(CoverView("closed", 0), setup, {WINDOW: "open"}, mem=mem, sun_auto=True, sun=True)
    assert _cover(CoverView("open", 70), setup, {WINDOW: "closed"}, mem=mem, sun_auto=True, sun=True) == []
    assert mem["sun_state"] == "foreign"
    assert _cover(CoverView("open", 70), setup, {WINDOW: "closed"}, mem=mem, sun_auto=True, sun=True) == []


def test_sun_protection_waits_for_the_window_and_closes_afterwards() -> None:
    setup, mem = CoverSetup([WINDOW], [WINDOW], []), {}
    assert _cover(CoverView("open", 100), setup, {WINDOW: "open"}, mem=mem, sun_auto=True, sun=True) == []
    assert _cover(CoverView("open", 100), setup, {WINDOW: "closed"}, mem=mem, sun_auto=True, sun=True) == CLOSE
    assert mem["sun_state"] == "ours"
    # the sun has left: reopened because FreshAirIQ closed it
    assert _cover(CoverView("closed", 0), setup, {WINDOW: "closed"}, mem=mem, sun_auto=True, sun=False) == OPEN


def test_sun_protection_only_reopens_what_it_closed() -> None:
    setup = CoverSetup([WINDOW], [], [])
    mem: dict = {}
    assert _cover(CoverView("open", 100), setup, {WINDOW: "open"}, mem=mem, sun_auto=True, sun=True) == CLOSE  # plain window: closes
    assert _cover(CoverView("closed", 0), setup, {WINDOW: "open"}, mem=mem, sun_auto=True, sun=True) == []
    # someone opened it meanwhile: no reopen command needed / no fight
    assert _cover(CoverView("open", 100), setup, {WINDOW: "open"}, mem=mem, sun_auto=True, sun=False) == []
    # already closed by the user: stays closed after the sun is gone
    mem = {}
    assert _cover(CoverView("closed", 0), setup, {}, mem=mem, sun_auto=True, sun=True) == []
    assert _cover(CoverView("closing"), setup, {}, mem={}, sun_auto=True, sun=True) == []
    assert _cover(CoverView("closed", 0), setup, {}, mem=mem, sun_auto=True, sun=False) == []
    # sun protection switched off: memory dropped
    mem = {"sun_state": "ours"}
    assert _cover(CoverView("closed", 0), setup, {}, mem=mem) == [] and mem == {}
    assert _cover(CoverView("unavailable"), setup, {}, mem=mem, sun_auto=True, sun=True) == []


def test_passage_door_never_closes_while_open() -> None:
    setup = CoverSetup([DOOR], [], [DOOR])
    mem: dict = {}
    # sun protection waits while the door is open (or its state is unknown)
    for mode in ("open", "tilted", "unknown"):
        assert _cover(CoverView("open", 100), setup, {DOOR: mode}, mem=mem, sun_auto=True, sun=True) == []
    assert _cover(CoverView("open", 100), setup, {DOOR: "closed"}, mem=mem, sun_auto=True, sun=True) == CLOSE
    # a close started by someone else is stopped and reversed
    assert _cover(CoverView("closing", 60), setup, {DOOR: "open"}, mem={}, sun_auto=True) == [(COVER_STOP, None), (COVER_OPEN, None)]
    follow = CoverSetup([DOOR], [DOOR], [DOOR])
    assert _cover(CoverView("closing", 60), follow, {DOOR: "open"}, mem={}) == [(COVER_STOP, None), (COVER_OPEN, None)]
    assert _cover(CoverView("closing", 60), setup, {DOOR: "open"}, mem={}) == [(COVER_STOP, None), (COVER_OPEN, None)]
    # door closed: closing is fine
    assert _cover(CoverView("closing", 60), follow, {DOOR: "closed"}, mem={}) == []


def test_restore_waits_for_a_separate_passage_door() -> None:
    setup, mem = CoverSetup([WINDOW, DOOR], [WINDOW], [DOOR]), {}
    _cover(CoverView("closed", 0, supports_position=True), setup, {WINDOW: "open", DOOR: "closed"}, mem=mem)
    assert _cover(CoverView("open", 100, supports_position=True), setup, {WINDOW: "closed", DOOR: "open"}, mem=mem) == []
    assert mem["follow_active"] is True
    assert _cover(CoverView("open", 100, supports_position=True), setup, {WINDOW: "closed", DOOR: "closed"}, mem=mem) == [(COVER_POSITION, 0)]


def test_fan_demand() -> None:
    assert fan_demand(FAN_CONTROL_MOISTURE_SOURCE, source_active=True, recommendation="okay", window_open=True)
    assert not fan_demand(FAN_CONTROL_MOISTURE_SOURCE, source_active=False, recommendation="ventilate", window_open=False)
    assert fan_demand(FAN_CONTROL_RECOMMENDATION, source_active=False, recommendation="continue_ventilating", window_open=False)
    assert not fan_demand(FAN_CONTROL_RECOMMENDATION, source_active=True, recommendation="ventilate", window_open=True)
    assert not fan_demand(FAN_CONTROL_OFF, source_active=True, recommendation="ventilate", window_open=False)


T0 = datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc)


def _fan(mem, *, fan_on, demand, minutes, mode=FAN_CONTROL_MOISTURE_SOURCE):
    return decide_fan(mode=mode, fan_on=fan_on, demand=demand, now=T0 + timedelta(minutes=minutes),
                      follow_up_min=10, max_runtime_min=60, mem=mem)


def test_fan_after_moisture_source_with_follow_up() -> None:
    mem: dict = {}
    assert _fan(mem, fan_on=None, demand=True, minutes=0) is None
    assert _fan(mem, fan_on=False, demand=True, minutes=0) == "on"
    assert _fan(mem, fan_on=True, demand=True, minutes=12) is None
    assert _fan(mem, fan_on=True, demand=False, minutes=20) is None  # 8 min follow-up so far
    assert _fan(mem, fan_on=True, demand=False, minutes=22) == "off"
    assert mem["owned"] is False


def test_fan_maximum_runtime_and_manual_off() -> None:
    mem: dict = {}
    _fan(mem, fan_on=False, demand=True, minutes=0)
    assert _fan(mem, fan_on=True, demand=True, minutes=60) == "off"
    assert _fan(mem, fan_on=False, demand=True, minutes=61) is None  # blocked until the source ends
    assert _fan(mem, fan_on=False, demand=False, minutes=70) is None
    assert _fan(mem, fan_on=False, demand=True, minutes=80) == "on"
    # switched off by hand: stays off until the source has ended
    assert _fan(mem, fan_on=False, demand=True, minutes=81) is None and mem["blocked"] is True
    assert _fan(mem, fan_on=False, demand=True, minutes=82) is None


def test_fan_started_by_hand_is_never_switched_off() -> None:
    mem: dict = {}
    assert _fan(mem, fan_on=True, demand=True, minutes=0) is None
    assert _fan(mem, fan_on=True, demand=False, minutes=30) is None


def test_fan_following_the_recommendation_and_switching_control_off() -> None:
    mem: dict = {}
    assert _fan(mem, fan_on=False, demand=True, minutes=0, mode=FAN_CONTROL_RECOMMENDATION) == "on"
    assert _fan(mem, fan_on=True, demand=False, minutes=1, mode=FAN_CONTROL_RECOMMENDATION) == "off"
    mem = {}
    _fan(mem, fan_on=False, demand=True, minutes=0)
    assert _fan(mem, fan_on=True, demand=False, minutes=1, mode=FAN_CONTROL_OFF) == "off"
    # broken timestamps fall back to "now"
    mem = {"owned": True, "since": "garbage", "last_demand": None}
    assert _fan(mem, fan_on=True, demand=False, minutes=0) is None
