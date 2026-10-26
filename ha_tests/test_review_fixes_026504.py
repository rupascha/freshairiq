"""0.26.5.4: fixes from the independent code review, in a real Home Assistant.

A04  bathroom with exhaust fan and neighbouring-room supply air: the mould
     indicator keeps the outdoor wall reference (before: warm hallway → risk hidden).
A02  a device that reports its switch-off a few seconds late: FreshAirIQ's own
     switch-off is "stopping", never "manual"; no "switch off the fan" push.
A05  two fans, one does not react: the switch-on is not confirmed (audit P1-06: "partial",
     FreshAirIQ keeps the fan that came on and switches it off later; P1-05: 1/2 on is visible).
A06  fan control switched off while FreshAirIQ runs the fan: switch-off recorded with its result
     (audit P2-08: followed until the fan reports off).
A10  the fan trace records how every command ended.
"""
from __future__ import annotations

from datetime import timedelta

from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S, FAN_OFF_CONFIRM_S
from custom_components.freshairiq.const import CONF_ROOM_CONTACTS, CONF_ROOM_EXHAUST_FAN, CONF_ROOM_EXHAUST_FAN_CONTROL
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.model import surface_relative_humidity

from ha_tests.test_actuator_control_20261017 import FAN as LIVE_FAN, _calls, _services
from ha_tests.test_cov_coordinator_b import OPTIONS, _cleanup_coordinators, _data, _make, _rooms  # noqa: F401
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _set_sources, _setup, _unload
from ha_tests.test_fan_automation_026504 import FAN, START, _controlled, _garage, _push


async def test_mould_indicator_keeps_the_outdoor_wall_reference_with_fan_supply_air(hass, freezer) -> None:
    rooms = _rooms()
    for room in rooms:
        if room["key"] == "buero":
            room.update(exhaust_fan_reference_temperature="sensor.flur_t1", exhaust_fan_reference_humidity="sensor.flur_h")
    d = await _make(hass, freezer, data=_data(rooms), options=OPTIONS, initial={"sensor.buero_h": (72.0, {"device_class": "humidity", "unit_of_measurement": "%"})})
    await d.step(60, fan__buero_abluft="on")
    await d.step(60)
    buero = d.room("buero")
    assert buero["reference_path"] == "neighbour_room"  # the airing compares with the hallway air
    factor = float(d.coordinator.options["surface_factor"])
    outdoor = surface_relative_humidity(buero["temperature"], buero["humidity"], 9.0, factor)
    hallway = surface_relative_humidity(buero["temperature"], buero["humidity"], 20.6, factor)
    assert abs(buero["surface_rh"] - outdoor) < 0.6 and outdoor - hallway > 5  # the wall still faces the 9 °C outdoor air


async def test_a_late_switch_off_report_is_no_manual_switch(hass, freezer) -> None:
    freezer.move_to(START)
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})], report=False)
    snapshot = coordinator.actuator_controller.fan_snapshot
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    hass.states.async_set(FAN, "on")  # the device reports a moment later
    freezer.tick(timedelta(seconds=3))
    await _push(hass, coordinator, "garage", house_aligned_action="continue_ventilating")
    assert snapshot("garage")["command_state"] == "confirmed"
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    freezer.tick(timedelta(seconds=FAN_OFF_CONFIRM_S + 1))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert [s for s, _ in log] == ["turn_on", "turn_off"]
    # off sent, the device still reports "on"
    garage = {**coordinator.data["rooms"]["garage"], "house_aligned_action": "close"}
    garage["configured_actuators"] = {**garage["configured_actuators"], "mechanical_exhaust_active": True}
    automation = room_fan_automation(garage, snapshot("garage"))
    assert automation["state"] == "stopping" and automation["user_action_needed"] is False
    hass.states.async_set(FAN, "off")
    freezer.tick(timedelta(seconds=4))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert snapshot("garage")["command_state"] == "confirmed"
    trace = [(row["command"], row["result"]) for row in coordinator.actuator_controller.fan_trace()]
    assert trace == [("on", "pending"), ("on", "confirmed"), ("off", "pending"), ("off", "confirmed")]
    await _unload(hass, entry)


async def test_two_fans_one_does_not_react(hass, freezer) -> None:
    freezer.move_to(START)
    second = "switch.garage_luefter_2"
    hass.states.async_set(FAN, "off")
    hass.states.async_set(second, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: [], CONF_ROOM_EXHAUST_FAN: [FAN, second]})], report=False)
    snapshot = coordinator.actuator_controller.fan_snapshot
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    hass.states.async_set(FAN, "on")  # only the first fan starts
    freezer.tick(timedelta(seconds=5))
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    assert snapshot("garage")["command_state"] == "pending"
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S))
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    snap = snapshot("garage")
    assert (snap["command_state"], snap["owned"], snap["fans_on"], snap["fans_total"]) == ("partial", True, 1, 2)
    assert coordinator.actuator_controller.fan_trace()[-1]["result"] == "partial"
    # the demand ends: FreshAirIQ switches off the group it started (the first fan never ran unattended)
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    freezer.tick(timedelta(seconds=FAN_OFF_CONFIRM_S + 1))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert [s for s, _ in log] == ["turn_on", "turn_on", "turn_off", "turn_off"]  # one group command each (two fans)
    await _unload(hass, entry)


async def test_switching_the_control_off_records_the_switch_off(hass) -> None:
    calls = _services(hass)
    _set_sources(hass, "wohnzimmer")
    hass.states.async_set(LIVE_FAN, "off")
    room = {**_room(), CONF_ROOM_EXHAUST_FAN: [LIVE_FAN], CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation"}
    entry = await _setup(hass, _entry(rooms=[room]))
    coordinator = entry.runtime_data
    controller = coordinator.actuator_controller
    coordinator.data["rooms"]["wohnzimmer"]["house_aligned_action"] = "ventilate_indirectly"
    await controller.async_reload()
    await hass.async_block_till_done()
    assert _calls(calls["turn_on"]) == [([LIVE_FAN], None)]
    hass.states.async_set(LIVE_FAN, "on")  # the fan runs
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [{**room, CONF_ROOM_EXHAUST_FAN_CONTROL: "off"}]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert _calls(calls["turn_off"]) == [([LIVE_FAN], None)]
    last = controller.fan_trace()[-1]
    assert (last["command"], last["result"], last["reason"], last["mode"]) == ("off", "pending", "control_removed", "off")
    hass.states.async_set(LIVE_FAN, "off")  # the device reports the switch-off
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    last = controller.fan_trace()[-1]
    assert (last["command"], last["result"], last["reason"]) == ("off", "confirmed", "control_removed")
    assert _calls(calls["turn_on"]) == [([LIVE_FAN], None)]  # no new automatic control without opt-in
    await _unload(hass, entry)
