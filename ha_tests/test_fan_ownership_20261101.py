"""Hotfix 01.11. (A1/A2): which fan FreshAirIQ switches when users switch shared and private fans by hand.

A1  Room A has [shared, private], room B [shared]. A ends, B still needs the shared fan: only
    the private fan goes off (correct). The user switches the private fan on again by hand. When
    B ends, FreshAirIQ sent turn_off([shared, private]) – the private fan is the user's now.
A2  A and B share one fan. A started it, A ends, B still needs it, the user switches it off by
    hand: B switched it on again in the next cycle (only A had noticed the manual switch-off).

Real controller, Home Assistant states and recorded service calls (exact entity lists).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ha_tests.test_audit_026504c import PRIVATE, SHARED, _controller, _room, _services

START = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
THIRD = "switch.third_fan"


async def _cycle(hass, freezer, coordinator, controller, minutes: float = 0.5, rec: dict | None = None, **sources: bool) -> None:
    freezer.tick(timedelta(minutes=minutes))
    rooms = {key: {"moisture_source_active": active} for key, active in sources.items()}
    for key, aligned in (rec or {}).items():
        rooms.setdefault(key, {})["house_aligned_action"] = aligned
    coordinator.data = {"rooms": rooms}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def _start(hass, freezer, rooms, fans=(SHARED, PRIVATE)):
    freezer.move_to(START)
    log = _services(hass)
    for fan in fans:
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, rooms)
    return log, coordinator, controller


# --- A1 --------------------------------------------------------------------------------------------

async def test_a1_a_private_fan_switched_on_again_by_hand_is_not_switched_off_with_the_group(hass, freezer) -> None:
    log, coordinator, controller = await _start(hass, freezer, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    assert log == [("turn_on", [PRIVATE, SHARED])]
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)   # A done, B keeps the shared fan
    assert log[-1] == ("turn_off", [PRIVATE])
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)   # the private off is confirmed
    hass.states.async_set(PRIVATE, "on")                                     # the user wants it on again
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)  # B ends
    assert log[-1] == ("turn_off", [SHARED])                                # the shared fan only
    assert hass.states.get(PRIVATE).state == "on" and hass.states.get(SHARED).state == "off"
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=2, a=False, b=False)
    assert all(PRIVATE not in entities for service, entities in log[2:] if service == "turn_off")
    # a new automatic start of A takes the whole group over again – and switches it off as a whole later
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    assert log[-1] == ("turn_on", [PRIVATE, SHARED])
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)
    assert log[-1] == ("turn_off", [PRIVATE, SHARED])
    await controller.async_stop()


async def test_a1_without_a_manual_switch_the_group_ends_as_before(hass, freezer) -> None:
    rooms = [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])]
    log, coordinator, controller = await _start(hass, freezer, rooms)
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)
    assert log[-1] == ("turn_off", [PRIVATE])
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)
    assert log[-1] == ("turn_off", [PRIVATE, SHARED])  # unchanged: the group as before (the private fan is still off)
    await controller.async_stop()


async def test_a1_the_released_private_fan_survives_a_restart(hass, freezer) -> None:
    rooms = [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])]
    log, coordinator, controller = await _start(hass, freezer, rooms)
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)   # the private off is confirmed
    memory = controller._memory                                            # what the store keeps over a restart
    await controller.async_stop()
    hass.states.async_set(PRIVATE, "on")                                    # switched on by hand meanwhile
    _entry, coordinator2, controller2 = await _controller(hass, rooms, entry_id="audit-restart")
    controller2._memory = memory
    await _cycle(hass, freezer, coordinator2, controller2, a=False, b=True)
    await _cycle(hass, freezer, coordinator2, controller2, a=False, b=False)  # B ends after the restart
    assert log[-1] == ("turn_off", [SHARED]) and hass.states.get(PRIVATE).state == "on"
    await controller2.async_stop()


async def test_a1_three_rooms_a_pending_private_off_and_a_failed_one(hass, freezer) -> None:
    rooms = [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED]), _room("c", [SHARED, THIRD])]
    log, coordinator, controller = await _start(hass, freezer, rooms, fans=(SHARED, PRIVATE, THIRD))
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True, c=True)
    assert log == [("turn_on", [PRIVATE, SHARED])]   # A started first; C's private fan is C's to start
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True, c=True)
    assert ("turn_off", [PRIVATE]) in log
    # B and C end in the same cycle while A's private switch-off is still pending (not confirmed yet):
    # nothing was switched on by hand – the group switch-off may include it
    hass.states.async_set(PRIVATE, "on")  # the device has not reported "off" yet
    await _cycle(hass, freezer, coordinator, controller, minutes=0.1, a=False, b=False, c=False)
    assert log[-1][0] == "turn_off" and SHARED in log[-1][1]
    await controller.async_stop()


# --- A2 --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("order", ["ab", "ba"])
async def test_a2_a_shared_fan_switched_off_by_hand_is_not_restarted_by_the_other_room(hass, freezer, order) -> None:
    rooms = [_room("a", [SHARED]), _room("b", [SHARED])]
    if order == "ba":
        rooms.reverse()   # B is evaluated before A in each cycle
    log, coordinator, controller = await _start(hass, freezer, rooms, fans=(SHARED,))
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    assert log == [("turn_on", [SHARED])]
    owner = "a" if order == "ab" else "b"
    other = "b" if owner == "a" else "a"
    await _cycle(hass, freezer, coordinator, controller, **{owner: False, other: True})   # the owner is done
    hass.states.async_set(SHARED, "off")                                                   # switched off by hand
    for _ in range(4):
        await _cycle(hass, freezer, coordinator, controller, **{owner: False, other: True})
    assert log == [("turn_on", [SHARED])]   # no automatic restart while the other room's demand lasts
    assert controller.fan_snapshot(other)["blocked"] is True
    await _cycle(hass, freezer, coordinator, controller, **{owner: False, other: False})  # that demand ends
    await _cycle(hass, freezer, coordinator, controller, **{owner: False, other: True})   # a new moisture-source cycle
    assert log[-1] == ("turn_on", [SHARED])
    await controller.async_stop()


async def test_a2_three_rooms_and_a_private_fan_stays_controllable(hass, freezer) -> None:
    rooms = [_room("a", [SHARED]), _room("b", [SHARED]), _room("c", [SHARED]), _room("d", [THIRD])]
    log, coordinator, controller = await _start(hass, freezer, rooms, fans=(SHARED, THIRD))
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True, c=True, d=False)
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True, c=True, d=False)   # the start is reported
    hass.states.async_set(SHARED, "off")   # by hand, all three rooms still need it
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, a=True, b=True, c=True, d=False)
    assert log == [("turn_on", [SHARED])]
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True, c=True, d=True)   # an independent fan
    assert log[-1] == ("turn_on", [THIRD])
    await controller.async_stop()


async def test_a2_recommendation_mode_and_a_follow_up_time(hass, freezer) -> None:
    a = {**_room("a", [SHARED], mode="recommendation")}
    b = {**_room("b", [SHARED]), "exhaust_fan_follow_up_min": 10}
    log, coordinator, controller = await _start(hass, freezer, [a, b], fans=(SHARED,))
    await _cycle(hass, freezer, coordinator, controller, rec={"a": "ventilate"}, a=False, b=True)
    assert log == [("turn_on", [SHARED])]
    await _cycle(hass, freezer, coordinator, controller, rec={"a": "ventilate"}, a=False, b=False)   # B's follow-up runs
    hass.states.async_set(SHARED, "off")   # by hand during the follow-up, A's recommendation still says to air
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=1, rec={"a": "ventilate"}, a=False, b=False)
    assert log == [("turn_on", [SHARED])]
    await controller.async_stop()


async def test_a2_a_start_not_reported_yet_is_no_manual_switch_off(hass, freezer) -> None:
    freezer.move_to(START)
    log = _services(hass, report=False)   # the device reports nothing
    hass.states.async_set(SHARED, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED]), _room("b", [SHARED])])
    await _cycle(hass, freezer, coordinator, controller, minutes=0, a=True, b=True)
    await _cycle(hass, freezer, coordinator, controller, minutes=0.2, a=True, b=True)
    assert controller.fan_snapshot("b")["blocked"] is False  # waiting for the report, not "switched off by hand"
    await controller.async_stop()
