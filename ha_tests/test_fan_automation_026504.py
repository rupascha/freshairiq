"""0.26.5.4 hotfix: automatic exhaust-fan control in a real Home Assistant.

Support diagnosis 24.10. (garage): the fan went ON at 13:31:24 and OFF at
13:31:25 – the recommendation switched it, and the running fan changed the
recommendation. Here the whole chain runs for real: recommendation → fan
request → Home Assistant state → new room evaluation → notification →
dashboard data and events. A simulated switch reports its new state like a
real device; the notify service records what the user would receive.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json

from homeassistant.core import ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S, FAN_OFF_CONFIRM_S
from custom_components.freshairiq.const import (
    CONF_ROOM_CONTACTS,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_FAN_CONTROL,
    CONF_ROOM_EXHAUST_FAN_FOLLOW_UP,
    DOMAIN,
)
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.model import absolute_humidity
from ha_tests.test_cov_setup_and_platforms import _entry, _room, _setup, _unload

FAN = "switch.garage_luefter"
DOOR = "binary_sensor.garage_tor"
START = datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc)
NOTIFY = {
    "notifications_enabled": True, "notification_targets": ["notify.phone"], "notification_scope": "both",
    "notification_cooldown_min": 1, "notify_ventilate": True, "notify_close": True, "notify_cooling": True,
    "notify_mould": False, "notify_sensor": False, "night_start_hour": "04:00", "night_end_hour": "04:30",
}


def _switch(hass, log: list, *, report: bool = True) -> None:
    """``homeassistant.turn_on/off`` like a real switch (optionally never reporting back)."""
    def handler(service: str):
        async def run(call: ServiceCall) -> None:
            entities = call.data["entity_id"]
            for entity_id in [entities] if isinstance(entities, str) else entities:
                log.append((service, dt_util.utcnow()))
                if report:
                    hass.states.async_set(entity_id, "on" if service == "turn_on" else "off")
        return run
    for service in ("turn_on", "turn_off"):
        hass.services.async_register("homeassistant", service, handler(service))


def _climate(hass, *, garage_rh: float, outdoor_t: float = 10.0, outdoor_rh: float = 55.0, garage_t: float = 18.0) -> None:
    hass.states.async_set("sensor.outdoor_temperature", str(outdoor_t), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outdoor_humidity", str(outdoor_rh), {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.garage_temperature", str(garage_t), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.garage_humidity", f"{garage_rh:.1f}", {"unit_of_measurement": "%"})


def _garage(**extra) -> dict:
    room = {**_room("garage", "Garage"), CONF_ROOM_CONTACTS: [DOOR], CONF_ROOM_EXHAUST_FAN: FAN,
            CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation"}
    room.update(extra)
    return room


async def _cycle(hass, freezer, coordinator) -> None:
    """One coordinator cycle plus the state-change refreshes of the following seconds."""
    freezer.tick(timedelta(seconds=30))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    for _ in range(3):
        freezer.tick(timedelta(seconds=1))
        await asyncio.sleep(0)
        await hass.async_block_till_done()


async def test_garage_end_to_end_without_switching_cycles_and_without_manual_push(hass, freezer) -> None:
    freezer.move_to(START)
    log: list = []
    _switch(hass, log)
    pushes = async_mock_service(hass, "notify", "phone")
    events: dict[str, list] = {"freshairiq_room_action": [], "freshairiq_notification": [], "freshairiq_room_recommendation": []}
    for name, bucket in events.items():
        hass.bus.async_listen(name, lambda event, bucket=bucket: bucket.append(dict(event.data)))
    rh = 88.0
    _climate(hass, garage_rh=rh)
    hass.states.async_set(FAN, "off")
    hass.states.async_set(DOOR, "off", {"device_class": "door"})
    entry = await _setup(hass, _entry(rooms=[_garage()], options=NOTIFY))
    coordinator = entry.runtime_data
    states: list[str] = []
    for _ in range(140):  # 70 minutes
        if hass.states.get(FAN).state == "on":
            rh -= 0.4
        else:
            rh = min(rh + 0.1, 88.0)
        _climate(hass, garage_rh=rh)
        await _cycle(hass, freezer, coordinator)
        states.append((coordinator.data["rooms"]["garage"].get("fan_automation") or {}).get("state"))

    services = [service for service, _ in log]
    # 0.26.5.4 (support case): the fan room is judged by its own model, not by the end of a
    # house airing plan - the fan runs while it still dries the room and stops at its
    # maximum runtime (60 min): one start, one stop, no switching cycle.
    assert services == ["turn_on", "turn_off"]
    assert (log[1][1] - log[0][1]).total_seconds() >= 60 * 60
    assert [s for i, s in enumerate(states) if i == 0 or s != states[i - 1]] == ["running", "completed"]

    # what the user receives: no manual "switch off the fan" for a fan FreshAirIQ switches itself
    texts = [str(call.data.get("message")) + " " + str(call.data.get("title")) for call in pushes]
    assert texts and not any("switch off" in text.lower() or "ausschalten" in text for text in texts)
    assert any(e["type"] == "fan_auto" for e in events["freshairiq_notification"])
    assert not any(e["type"] == "close" and e.get("room_key") == "garage" for e in events["freshairiq_notification"])
    closes = [e for e in events["freshairiq_room_action"] if e["action"] == "close"]
    assert all(e["category"] == "status" and e["fan_automation"]["mode"] == "recommendation" for e in closes)

    # dashboard data, room entity payload and diagnostics carry the same automation state
    room = coordinator.data["rooms"]["garage"]
    assert room["configured_actuators"]["exhaust_fan_control"] == "recommendation"
    action_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_garage_action")
    payload = hass.states.get(action_id).attributes["freshairiq_room_payload"]
    assert payload["fan_automation"]["state"] == room["fan_automation"]["state"]
    trace = coordinator.data["fan_automation_trace"]
    # 0.26.5.4 (review A10): every command and how it ended
    assert [(f"turn_{row['command']}", row["result"]) for row in trace] == [
        (services[0], "pending"), (services[0], "confirmed"), (services[1], "pending"), (services[1], "confirmed")]
    assert [row["reason"] for row in trace] == ["recommendation", "recommendation", "max_runtime", "max_runtime"] and "switch." not in json.dumps(trace)
    record = coordinator.diagnostics._build_record(coordinator.data, coordinator.store.data, dt_util.now(), [], "test")
    assert record["fan_automation_trace"] == trace
    exported = next(r for r in record["rooms"] if r["key"] == "garage")
    assert exported["fan_automation"]["mode"] == "recommendation" and "switch." not in json.dumps(exported["fan_automation"])
    await _unload(hass, entry)


async def _controlled(hass, rooms: list[dict], *, report: bool = True, register: bool = True):
    log: list = []
    if register:
        _switch(hass, log, report=report)
    for room in rooms:
        _climate(hass, garage_rh=60.0)
        hass.states.async_set(f"sensor.{room['key']}_temperature", "20", {"unit_of_measurement": "°C"})
        hass.states.async_set(f"sensor.{room['key']}_humidity", "60", {"unit_of_measurement": "%"})
    entry = await _setup(hass, _entry(rooms=rooms))
    coordinator = entry.runtime_data

    async def _keep_injected_data():  # a fan state change must not recompute the injected room data
        return coordinator.data

    coordinator._async_update_data = _keep_injected_data
    return entry, coordinator, log


async def _push(hass, coordinator, key: str, **values) -> None:
    coordinator.data["rooms"][key].update(values)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()


async def test_continue_close_continue_within_a_second_switches_nothing(hass, freezer) -> None:
    freezer.move_to(START)
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})])
    await _push(hass, coordinator, "garage", house_aligned_action="continue_ventilating")
    assert [s for s, _ in log] == ["turn_on"]
    for action in ("close", "continue_ventilating", "close"):
        freezer.tick(timedelta(milliseconds=400))
        await _push(hass, coordinator, "garage", house_aligned_action=action)
    assert [s for s, _ in log] == ["turn_on"]
    freezer.tick(timedelta(seconds=FAN_OFF_CONFIRM_S))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert [s for s, _ in log] == ["turn_on", "turn_off"]  # a stable close ends it
    await _unload(hass, entry)


async def test_hand_switched_fans_and_shared_fans(hass, freezer) -> None:
    freezer.move_to(START)
    hass.states.async_set(FAN, "on")  # switched on by hand
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})])
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    freezer.tick(timedelta(minutes=5))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert log == []  # never taken over, never switched off
    await _unload(hass, entry)

    # a fan FreshAirIQ started and the user switched off stays off while the demand lasts
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})], register=False)
    calls = async_mock_service(hass, "homeassistant", "turn_on")
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    hass.states.async_set(FAN, "on")
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    hass.states.async_set(FAN, "off")
    for _ in range(3):
        freezer.tick(timedelta(minutes=1))
        await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    assert len(calls) == 1
    assert coordinator.actuator_controller.fan_snapshot("garage")["reason"] == "manual_off"
    await _unload(hass, entry)

    # one fan, two rooms: it stays on while one room still needs it
    hass.states.async_set(FAN, "off")
    flur = {**_room("flur", "Flur"), CONF_ROOM_CONTACTS: [], CONF_ROOM_EXHAUST_FAN: FAN, CONF_ROOM_EXHAUST_FAN_CONTROL: "recommendation"}
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []}), flur])
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    await _push(hass, coordinator, "flur", house_aligned_action="ventilate_indirectly")
    freezer.tick(timedelta(minutes=2))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    freezer.tick(timedelta(minutes=2))
    await _push(hass, coordinator, "garage", house_aligned_action="close")
    assert [s for s, _ in log] == ["turn_on"] and hass.states.get(FAN).state == "on"
    await _unload(hass, entry)


async def test_pending_and_failed_commands_are_not_reported_as_done(hass, freezer) -> None:
    freezer.move_to(START)
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})], report=False)
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    snapshot = coordinator.actuator_controller.fan_snapshot
    assert (snapshot("garage")["command"], snapshot("garage")["command_state"]) == ("on", "pending")
    garage = coordinator.data["rooms"]["garage"]
    assert room_fan_automation(garage, snapshot("garage"))["state"] == "requested"
    freezer.tick(timedelta(seconds=5))
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    assert snapshot("garage")["owned"] is True  # a late report is no manual switch-off
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S))
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    assert snapshot("garage")["command_state"] == "failed"
    automation = room_fan_automation(garage, snapshot("garage"))
    assert automation["state"] == "failed" and automation["user_action_needed"] is True
    assert automation["label"] == "Ablüfter konnte nicht automatisch eingeschaltet werden – bitte von Hand einschalten"
    await _unload(hass, entry)

    # a service that is missing fails at once
    for service in ("turn_on", "turn_off"):
        hass.services.async_remove("homeassistant", service)
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})], register=False)
    await _push(hass, coordinator, "garage", house_aligned_action="ventilate_indirectly")
    assert snapshot_state(coordinator) == ("failed", False)
    assert coordinator.actuator_controller.fan_trace()[-1]["result"] == "failed"
    await _unload(hass, entry)


def snapshot_state(coordinator) -> tuple:
    snap = coordinator.actuator_controller.fan_snapshot("garage")
    return snap["command_state"], snap["owned"]


async def test_moisture_source_mode_with_flickering_recommendation_and_follow_up(hass, freezer) -> None:
    freezer.move_to(START)
    hass.states.async_set(FAN, "off")
    room = _garage(**{CONF_ROOM_CONTACTS: [], CONF_ROOM_EXHAUST_FAN_CONTROL: "moisture_source", CONF_ROOM_EXHAUST_FAN_FOLLOW_UP: 5})
    entry, coordinator, log = await _controlled(hass, [room])
    await _push(hass, coordinator, "garage", moisture_source_active=True, house_aligned_action="close")
    for action in ("ventilate", "close", "continue_ventilating", "close"):
        freezer.tick(timedelta(seconds=20))
        await _push(hass, coordinator, "garage", moisture_source_active=True, house_aligned_action=action)
    assert [s for s, _ in log] == ["turn_on"]
    await coordinator.async_refresh()
    coordinator.data["rooms"]["garage"]["moisture_source_active"] = True
    await _push(hass, coordinator, "garage", moisture_source_active=False, house_aligned_action="close")
    freezer.tick(timedelta(minutes=4))
    await _push(hass, coordinator, "garage", moisture_source_active=False, house_aligned_action="ventilate")
    assert [s for s, _ in log] == ["turn_on"]  # follow-up time still running
    freezer.tick(timedelta(minutes=2))
    await _push(hass, coordinator, "garage", moisture_source_active=False, house_aligned_action="ventilate")
    assert [s for s, _ in log] == ["turn_on", "turn_off"]
    assert coordinator.actuator_controller.fan_snapshot("garage")["reason"] == "follow_up_ended"
    await _unload(hass, entry)


# --------------------------------------------------------------------------- neighbouring-room reference
def _bath(control: str) -> dict:
    return {**_room("bad", "Bad"), CONF_ROOM_CONTACTS: ["binary_sensor.bad_fenster"], CONF_ROOM_EXHAUST_FAN: "switch.bad_luefter",
            CONF_ROOM_EXHAUST_FAN_CONTROL: control, "exhaust_fan_reference_temperature": "sensor.flur_t",
            "exhaust_fan_reference_humidity": "sensor.flur_h"}


async def _heinzel(hass, freezer, *, control: str, flur_t: float, window: str = "off", fan: str = "off", bad_rh: float = 68,
                   outdoor_t: float = 16):
    """Community case (heinzel): bathroom 68 % (target 62 %), hallway 58 %, humid outdoor air."""
    freezer.move_to(START)
    log: list = []
    _switch(hass, log)
    hass.states.async_set("sensor.outdoor_temperature", str(outdoor_t), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outdoor_humidity", "97", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.bad_temperature", "22", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.bad_humidity", str(bad_rh), {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.flur_t", str(flur_t), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.flur_h", "58", {"unit_of_measurement": "%"})
    hass.states.async_set("binary_sensor.bad_fenster", window, {"device_class": "window"})
    hass.states.async_set("switch.bad_luefter", fan)
    entry = await _setup(hass, _entry(rooms=[_bath(control)], options={"target_rh": 62}))
    for _ in range(2):
        freezer.tick(timedelta(seconds=30))
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    return entry, entry.runtime_data.data["rooms"]["bad"], log


async def test_heinzel_bathroom_is_judged_on_the_air_the_fan_will_draw_in(hass, freezer) -> None:
    # absolute humidity decides, not relative: 68 % at 22 °C vs. 58 % at 20 °C vs. 97 % at 16 °C
    room_ah, hall_ah, outdoor_ah = absolute_humidity(22, 68), absolute_humidity(20, 58), absolute_humidity(16, 97)
    assert outdoor_ah > hall_ah and room_ah - hall_ah > 2.5 and room_ah - outdoor_ah < 0.5
    entry, room, log = await _heinzel(hass, freezer, control="recommendation", flur_t=20)
    # before 0.26.5.4 the stopped fan was judged on the outdoor air (hardly drier): no airing at all
    assert room["reference_path"] == "neighbour_room"
    assert round(room["reference_humidity"], 1) == round(hall_ah, 1)
    assert room["action"] == "Ventilate"
    # (the test server speaks English; German: "Vergleichsluft ist die Zuluft aus dem Nebenraum …")
    assert "The reference air is the air drawn in from the neighbouring room (exhaust fan), not the outdoor air" in room["recommendation_reasons"]
    # the house still asks for a minimum benefit (about 50 ml < 100 ml): it waits, the fan stays off
    assert room["house_aligned_action"] == "ventilate_later" and log == []
    assert room["fan_automation"]["state"] == "idle"
    await _unload(hass, entry)


async def test_humid_bathroom_starts_its_fan_although_the_outdoor_air_is_wetter(hass, freezer) -> None:
    assert absolute_humidity(22, 97) > absolute_humidity(22, 88) > absolute_humidity(20, 58)
    entry, room, log = await _heinzel(hass, freezer, control="recommendation", flur_t=20, bad_rh=88, outdoor_t=22)
    assert room["reference_path"] == "neighbour_room"
    assert [s for s, _ in log] == ["turn_on"]  # start decided on the neighbouring-room air …
    assert room["house_aligned_action"] == "continue_ventilating" and room["reference_path"] == "neighbour_room"  # … and no switch once running
    await _unload(hass, entry)
    entry, room, log = await _heinzel(hass, freezer, control="off", flur_t=20, bad_rh=88, outdoor_t=22)
    assert room["reference_path"] == "default" and room["action"] in {"Do not ventilate", "Wait"}  # manual fan: window air as before
    await _unload(hass, entry)


async def test_heinzel_bathroom_with_a_warm_hallway_does_not_start(hass, freezer) -> None:
    # 58 % at 25 °C holds more water than 68 % at 22 °C: no drying advantage, no start
    assert absolute_humidity(25, 58) > absolute_humidity(22, 68)
    entry, room, log = await _heinzel(hass, freezer, control="recommendation", flur_t=25)
    assert room["reference_path"] == "neighbour_room" and room["action"] != "Ventilate" and log == []
    await _unload(hass, entry)


async def test_reference_paths_of_window_manual_fan_and_running_fan(hass, freezer) -> None:
    entry, room, log = await _heinzel(hass, freezer, control="off", flur_t=20)
    assert room["reference_path"] == "default" and room["action"] != "Ventilate"  # manual fan: window air, unchanged
    await _unload(hass, entry)
    entry, room, log = await _heinzel(hass, freezer, control="off", flur_t=20, fan="on")
    assert room["reference_path"] == "neighbour_room"  # running fan, window closed
    await _unload(hass, entry)
    entry, room, log = await _heinzel(hass, freezer, control="recommendation", flur_t=20, window="on")
    assert room["reference_path"] == "default" and log == []  # window open: its own air, no automatic fan
    await _unload(hass, entry)


async def test_damaged_values_never_break_the_fan_control(hass, freezer) -> None:
    from custom_components.freshairiq.actuator_controller import _co2_critical, _moisture_coming_in

    assert _moisture_coming_in({"active": True, "moisture_effect_next_5_min_ml": -3}) is True
    assert _moisture_coming_in({"active": True, "moisture_effect_next_5_min_ml": "x"}) is False
    assert _moisture_coming_in({"active": False, "moisture_effect_next_5_min_ml": -3}) is False
    assert _co2_critical({"co2": 1500}, {}) is True and _co2_critical({"co2": None}, {}) is False
    assert _co2_critical({"co2": 1500, "co2_available": False}, {}) is False
    freezer.move_to(START)
    hass.states.async_set(FAN, "off")
    entry, coordinator, log = await _controlled(hass, [_garage(**{CONF_ROOM_CONTACTS: []})])
    controller = coordinator.actuator_controller
    assert controller._restart_locked("garage", {"completed_at": "2026-13-45T99:00:00"}) is False
    assert controller._restart_locked("garage", {"completed_at": dt_util.now().isoformat()}) is True
    assert controller._restart_locked("unknown", {"completed_at": dt_util.now().isoformat()}) is False
    assert controller.fan_snapshot("unknown")["owned"] is False
    await _unload(hass, entry)
