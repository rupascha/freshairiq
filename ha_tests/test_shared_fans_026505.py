"""0.26.5.5 (community diagnosis 28.10.): fans several rooms share, in a real Home Assistant.

* a room's follow-up time keeps a shared fan running although the room that switched
  it on has no demand any more (before: switched off at once);
* the maximum runtime protects the device also while another room still needs it
  (before: skipped), and that room does not restart it until its own demand ends;
* every room shows the shared fan as FreshAirIQ's ("shared"), never as switched on by
  hand ("manual" asked the user to switch it off);
* another automation (Alexa, washing machine …) can take the fans over with a switch,
  helper or timer: FreshAirIQ then sends nothing and never switches them off.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.fan_automation import auto_stop, room_fan_automation
from ha_tests.test_audit_026504c import SHARED, _controller, _room, _services

START = datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc)
SECOND = "switch.second_fan"


def _rooms(**extra):
    a = {**_room("a", [SHARED, SECOND]), **extra.get("a", {})}
    b = {**_room("b", [SHARED, SECOND]), **extra.get("b", {})}
    return [a, b]


async def _cycle(hass, freezer, coordinator, controller, minutes: float = 0.5, **sources: bool) -> None:
    freezer.tick(timedelta(minutes=minutes))
    coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


def _automation(controller, key: str, *, aligned: str = "close", fan_on: bool = True) -> dict:
    room = {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": [SHARED, SECOND], "mechanical_exhaust_active": fan_on},
            "house_aligned_action": aligned}
    return room_fan_automation(room, controller.fan_snapshot(key))


async def _start(hass, freezer, rooms):
    freezer.move_to(START)
    log = _services(hass)
    for fan in (SHARED, SECOND):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, rooms)
    return log, coordinator, controller


async def test_the_follow_up_of_another_room_keeps_the_shared_fans(hass, freezer) -> None:
    log, coordinator, controller = await _start(hass, freezer, _rooms(b={"exhaust_fan_follow_up_min": 10}))
    before = controller.fan_snapshot("a")  # nothing needed yet: no times at all
    assert before["follow_up_until"] is None and before["runtime_limit_at"] is None
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    assert log == [("turn_on", [SECOND, SHARED])] and controller.fan_snapshot("a")["owned"]
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)   # both sources ended
    await _cycle(hass, freezer, coordinator, controller, minutes=5, a=False, b=False)
    assert len(log) == 1  # B's 10-minute follow-up still runs
    state = _automation(controller, "a")
    assert state["state"] == "shared" and state["label_key"] == "shared_for" and not state["user_action_needed"]
    # a real countdown: B's last demand (first cycle, 11:00:30) + its 10-minute follow-up; the device limit of the owner
    assert datetime.fromisoformat(state["follow_up_until"]) == START + timedelta(seconds=30, minutes=10)
    assert datetime.fromisoformat(state["runtime_limit_at"]) == START + timedelta(seconds=30, minutes=240)
    await _cycle(hass, freezer, coordinator, controller, minutes=6, a=False, b=False)
    assert log[-1] == ("turn_off", [SECOND, SHARED])  # after the last valid follow-up
    await controller.async_stop()


async def test_two_follow_up_times_end_with_the_later_one(hass, freezer) -> None:
    rooms = _rooms(a={"exhaust_fan_follow_up_min": 4}, b={"exhaust_fan_follow_up_min": 12})
    log, coordinator, controller = await _start(hass, freezer, rooms)
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)
    await _cycle(hass, freezer, coordinator, controller, minutes=6, a=False, b=False)   # A's own follow-up is over
    assert len(log) == 1
    await _cycle(hass, freezer, coordinator, controller, minutes=7, a=False, b=False)   # B's too
    assert log[-1][0] == "turn_off"
    await controller.async_stop()


async def test_the_maximum_runtime_also_applies_while_another_room_needs_the_fans(hass, freezer) -> None:
    rooms = _rooms(a={"exhaust_fan_max_runtime_min": 30})
    log, coordinator, controller = await _start(hass, freezer, rooms)
    await _cycle(hass, freezer, coordinator, controller, a=True, b=True)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=True)   # A done, B still needs the fans
    assert len(log) == 1
    assert _automation(controller, "b", aligned="ventilate")["state"] == "shared"
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=10, a=False, b=True)
    assert log[-1] == ("turn_off", [SECOND, SHARED])  # device protection after 30 minutes
    assert any(row["reason"] == "max_runtime" and row["command"] == "off" for row in controller.fan_trace())
    for _ in range(3):
        await _cycle(hass, freezer, coordinator, controller, minutes=1, a=False, b=True)
    assert log[-1][0] == "turn_off"  # B does not start it again while its demand lasts
    await _cycle(hass, freezer, coordinator, controller, minutes=1, a=False, b=False)
    await _cycle(hass, freezer, coordinator, controller, minutes=1, a=False, b=True)
    assert log[-1][0] == "turn_on"  # a new demand starts it again
    await controller.async_stop()


async def test_the_other_room_shows_freshairiqs_fan_not_a_manual_one(hass, freezer) -> None:
    log, coordinator, controller = await _start(hass, freezer, _rooms())
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    state = _automation(controller, "b")
    # before: "manual" + user_action_needed → "Bitte Lüfter ausschalten" although FreshAirIQ runs it
    assert state["state"] == "shared" and state["label_key"] == "shared_owner" and not state["user_action_needed"]
    assert auto_stop({"fan_automation": state})
    # a fan switched on by hand in a room nobody controls stays "manual"
    hass.states.async_set(SHARED, "on")
    log2, coordinator2, controller2 = await _start(hass, freezer, [_room("c", [SHARED, SECOND])])
    hass.states.async_set(SHARED, "on")
    await _cycle(hass, freezer, coordinator2, controller2, c=False)
    assert room_fan_automation({"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": [SHARED, SECOND], "mechanical_exhaust_active": True},
                                "house_aligned_action": "close"}, controller2.fan_snapshot("c"))["state"] == "manual"
    await controller.async_stop()
    await controller2.async_stop()


async def test_another_automation_takes_the_fans_over(hass, freezer) -> None:
    lock = "input_boolean.alexa_luefter"
    hass.states.async_set(lock, "off")
    log, coordinator, controller = await _start(hass, freezer, _rooms(a={"exhaust_fan_external_lock": lock}))
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    assert log == [("turn_on", [SECOND, SHARED])]
    hass.states.async_set(lock, "on")   # Alexa sends "on" to the running fans and starts its own follow-up
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)
    await _cycle(hass, freezer, coordinator, controller, minutes=20, a=False, b=False)
    assert len(log) == 1  # FreshAirIQ switches nothing off while the other automation runs it
    state = _automation(controller, "a")
    assert state["state"] == "external" and not state["user_action_needed"] and not controller.fan_snapshot("a")["owned"]
    hass.states.async_set(lock, "off")   # the other automation is done – the fans are no longer FreshAirIQ's
    await _cycle(hass, freezer, coordinator, controller, minutes=5, a=False, b=False)
    assert len(log) == 1
    for fan in (SHARED, SECOND):
        hass.states.async_set(fan, "off")
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    assert log[-1][0] == "turn_on"  # a new demand later is FreshAirIQ's again
    await controller.async_stop()


async def test_a_timer_counts_while_active_or_paused(hass, freezer) -> None:
    timer = "timer.trockner_nachlauf"
    log, coordinator, controller = await _start(hass, freezer, [_room("a", [SHARED, SECOND]) | {"exhaust_fan_external_lock": timer}])
    for state, locked in (("active", True), ("paused", True), ("idle", False)):
        hass.states.async_set(timer, state)
        assert controller._locked(controller._rooms[0]) is locked
    hass.states.async_set(timer, "unavailable")
    assert controller._locked(controller._rooms[0]) is False
    await controller.async_stop()


def test_the_lock_field_is_saved_cleared_and_kept() -> None:
    from custom_components.freshairiq.config_flow_rooms import _normalise_room_control

    previous = {"exhaust_fan_external_lock": "input_boolean.alexa"}
    room = {"exhaust_fan_control": "recommendation", "exhaust_fan_external_lock": " timer.trockner "}
    _normalise_room_control(room, previous)
    assert room["exhaust_fan_external_lock"] == "timer.trockner"
    cleared = {"exhaust_fan_control": "recommendation"}  # the automation form was sent with an empty field
    _normalise_room_control(cleared, previous)
    assert cleared["exhaust_fan_external_lock"] is None
    other_form = {}  # a form without the automation settings keeps the stored value
    _normalise_room_control(other_form, previous)
    assert other_form["exhaust_fan_external_lock"] == "input_boolean.alexa"


async def test_whole_chain_no_switch_off_push_while_another_room_needs_the_shared_fan(hass, freezer) -> None:
    """Room evaluation → house advice → fan ownership → notification → notify service, with a shared fan."""
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_mock_service

    from ha_tests.test_cov_setup_and_platforms import _entry, _setup, _unload
    from ha_tests.test_fan_automation_026504 import FAN, NOTIFY, _climate, _cycle as _real_cycle, _garage, _switch
    from ha_tests.test_cov_setup_and_platforms import _room as _base_room

    freezer.move_to(START)
    log: list = []
    _switch(hass, log)
    pushes = async_mock_service(hass, "notify", "phone")
    rh = 88.0
    _climate(hass, garage_rh=rh)
    hass.states.async_set("sensor.flur_temperature", "18", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.flur_humidity", "48", {"unit_of_measurement": "%"})
    hass.states.async_set(FAN, "off")
    hass.states.async_set("binary_sensor.garage_tor", "off", {"device_class": "door"})
    flur = {**_base_room("flur", "Flur"), "contacts": [], "exhaust_fan": FAN, "exhaust_fan_control": "recommendation"}
    entry = await _setup(hass, _entry(rooms=[_garage(), flur], options=NOTIFY))
    coordinator = entry.runtime_data
    states = set()
    for _ in range(40):  # 20 minutes: the garage still dries, the hallway has nothing to do
        if hass.states.get(FAN).state == "on":
            rh -= 0.2
        _climate(hass, garage_rh=rh)
        await _real_cycle(hass, freezer, coordinator)
        states.add((coordinator.data["rooms"]["flur"].get("fan_automation") or {}).get("state"))
    assert [s for s, _ in log][:1] == ["turn_on"]
    texts = [f"{call.data.get('title')} {call.data.get('message')}" for call in pushes]
    assert not [t for t in texts if "Flur" in t and ("ausschalten" in t or "switch off" in t.lower())], texts
    assert "manual" not in states  # the hallway never shows FreshAirIQ's fan as switched on by hand
    assert dt_util.now() > START
    await _unload(hass, entry)


@pytest.mark.parametrize("control", ["moisture_source", "off"])
async def test_f01_a_lock_in_another_room_protects_the_shared_device(hass, freezer, control) -> None:
    """Room B's automation lock covers the shared fan – room A neither switches it off nor on (F01).

    A's private fan stays A's; B may even have no automatic control of its own.
    """
    from ha_tests.test_audit_026504c import PRIVATE

    lock = "input_boolean.alexa_trockner"
    a = _room("a", [SHARED, PRIVATE])
    b = {**_room("b", [SHARED], mode=control), "exhaust_fan_external_lock": lock}
    hass.states.async_set(lock, "off")
    log, coordinator, controller = await _start(hass, freezer, [a, b])
    hass.states.async_set(PRIVATE, "off")
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    assert log == [("turn_on", [PRIVATE, SHARED])]
    hass.states.async_set(lock, "on")   # the dryer automation takes the shared fan over (for room B)
    await _cycle(hass, freezer, coordinator, controller, a=False, b=False)
    await _cycle(hass, freezer, coordinator, controller, minutes=5, a=False, b=False)
    assert ("turn_off", [SHARED]) not in log and all(SHARED not in entities for service, entities in log[1:])
    assert log[-1] == ("turn_off", [PRIVATE])  # only A's own fan
    assert hass.states.get(SHARED).state == "on"
    hass.states.async_set(SHARED, "off")  # the automation is done and switched it off itself
    await _cycle(hass, freezer, coordinator, controller, a=True, b=False)
    assert all(SHARED not in entities for service, entities in log[1:])  # still locked: never switched on either
    await controller.async_stop()
