"""0.26.5.5 hotfix (Waschküche with two exhaust fans): controller → Home Assistant service → state feedback
→ fan_snapshot → fan_automation, in a real Home Assistant.

F1  a fan another room still holds (follow-up) is not switched off when a room's control is removed,
    and fans dropped from a room's list are switched off;
F2  a deferred switch-off is per device: a free fan goes off while a fan still held keeps running;
F3  "Lüftungsziel erreicht" first says that FreshAirIQ checks before switching off (no switch-off sent
    yet); "beendet die Lüftung" only once the command is sent; "abgeschlossen" only when every fan is off;
F4  a group start where one fan did not come on is retried once; a group partly switched on by hand
    is never taken over.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.core import ServiceCall

from custom_components.freshairiq.close_wording import fan_stop_message
from custom_components.freshairiq.fan_automation import auto_stop, room_fan_automation
from ha_tests.test_audit_026504c import _controller, _room, _services

START = datetime(2026, 10, 30, 11, 0, tzinfo=timezone.utc)
X, Y = "switch.waschkueche_fan_1", "switch.waschkueche_fan_2"


async def _tick(hass, freezer, coordinator, controller, seconds: float, **rooms) -> None:
    freezer.tick(timedelta(seconds=seconds))
    coordinator.data = {"rooms": rooms}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


def _src(active: bool) -> dict:
    return {"moisture_source_active": active}


def _rec(aligned: str) -> dict:
    return {"house_aligned_action": aligned, "configured_actuators": {"window_open": False}}


def _view(controller, key, fans, *, mode="recommendation", aligned="close", fan_on=None, hass=None):
    on = fan_on if fan_on is not None else any(hass.states.get(f).state == "on" for f in fans)
    room = {"configured_actuators": {"exhaust_fan_control": mode, "exhaust_fan": fans, "mechanical_exhaust_active": on},
            "house_aligned_action": aligned, "delta_g_m3": 0.2}
    room["fan_automation"] = room_fan_automation(room, controller.fan_snapshot(key))
    return room


async def _setup(hass, freezer, rooms, *, report=True):
    freezer.move_to(START)
    log = _services(hass, report=report)
    for fan in (X, Y):
        hass.states.async_set(fan, "off")
    entry, coordinator, controller = await _controller(hass, rooms, entry_id="hotfix")
    return log, entry, coordinator, controller


# --- F1 --------------------------------------------------------------------------------------

async def test_f1_removing_a_control_keeps_the_fan_another_room_still_holds(hass, freezer) -> None:
    rooms = [_room("bad", [X]), {**_room("wasch", [X]), "exhaust_fan_follow_up_min": 10}]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    await _tick(hass, freezer, coordinator, controller, 30, bad=_src(True), wasch=_src(False))
    assert log == [("turn_on", [X])] and controller.fan_snapshot("bad")["owned"]
    await _tick(hass, freezer, coordinator, controller, 30, bad=_src(True), wasch=_src(True))
    await _tick(hass, freezer, coordinator, controller, 30, bad=_src(False), wasch=_src(False))  # wasch: follow-up runs
    assert len(log) == 1
    # the bathroom's control is switched off while the laundry's follow-up still runs
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("bad", [X], mode="off"), rooms[1]]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert len(log) == 1 and hass.states.get(X).state == "on"  # before: switched off at once
    await _tick(hass, freezer, coordinator, controller, 5 * 60, wasch=_src(False))
    assert len(log) == 1
    await _tick(hass, freezer, coordinator, controller, 6 * 60, wasch=_src(False))  # follow-up over
    assert log[-1] == ("turn_off", [X]) and hass.states.get(X).state == "off"
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False))
    assert controller._memory["fans"]["bad"]["command_state"] == "confirmed"
    assert sum(1 for call in log if call[0] == "turn_off") == 1  # exactly one switch-off
    await controller.async_stop()


async def test_f1_a_fan_dropped_from_the_rooms_list_is_switched_off(hass, freezer) -> None:
    rooms = [_room("wasch", [X, Y])]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(True))
    assert log == [("turn_on", [X, Y])]
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("wasch", [X])]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [Y]) and hass.states.get(X).state == "on"  # before: Y ran on unattended
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False))
    assert log[-1] == ("turn_off", [X])
    # a reload with the same fan list changes nothing
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(True))
    calls = len(log)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [{**_room("wasch", [X]), "exhaust_fan_follow_up_min": 1}]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert len(log) == calls and controller.fan_snapshot("wasch")["owned"]
    await controller.async_stop()


# --- F2 --------------------------------------------------------------------------------------

async def test_f2_a_deferred_switch_off_is_per_device(hass, freezer) -> None:
    rooms = [_room("bad", [X, Y]), _room("wasch", [X, Y]), {**_room("keller", [X]), "exhaust_fan_follow_up_min": 10}]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    await _tick(hass, freezer, coordinator, controller, 30, bad=_src(True), wasch=_src(True), keller=_src(True))
    assert log == [("turn_on", [X, Y])] and controller.fan_snapshot("bad")["owned"]
    # the bathroom's control is removed while the laundry needs both fans: both are deferred
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("bad", [X, Y], mode="off"), *rooms[1:]]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert len(log) == 1 and sorted(controller._memory["fans"]["bad"]["deferred_off"]) == [X, Y]
    # the laundry is done; the cellar's follow-up still holds X – Y is free and goes off
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False), keller=_src(False))
    assert log[-1] == ("turn_off", [Y]) and hass.states.get(X).state == "on"  # before: neither went off
    mem = controller._memory["fans"]["bad"]
    assert mem["deferred_off"] == [X] and mem["command_state"] == "pending"
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False), keller=_src(False))
    assert controller._memory["fans"]["bad"]["command_state"] == "confirmed" and len(log) == 2
    await _tick(hass, freezer, coordinator, controller, 10 * 60, wasch=_src(False), keller=_src(False))  # follow-up over
    assert log[-1] == ("turn_off", [X]) and controller._memory["fans"]["bad"]["deferred_off"] is None
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False), keller=_src(False))
    assert controller._memory["fans"]["bad"]["command_state"] == "confirmed"
    assert [c for c in log if c[0] == "turn_off"] == [("turn_off", [Y]), ("turn_off", [X])]  # no double commands
    await controller.async_stop()


async def test_f2_a_locked_fan_is_kept_deferred_not_lost(hass, freezer) -> None:
    lock = "input_boolean.alexa_trockner"
    hass.states.async_set(lock, "off")
    rooms = [_room("bad", [X, Y]), {**_room("wasch", [X]), "exhaust_fan_external_lock": lock}]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    await _tick(hass, freezer, coordinator, controller, 30, bad=_src(True), wasch=_src(False))
    hass.states.async_set(lock, "on")  # another automation takes X over
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("bad", [X, Y], mode="off"), rooms[1]]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [Y]) and hass.states.get(X).state == "on"  # X belongs to the other automation
    assert controller._memory["fans"]["bad"]["deferred_off"] == [X]
    await _tick(hass, freezer, coordinator, controller, 90, wasch=_src(False))
    assert log[-1] == ("turn_off", [Y]) and controller._memory["fans"]["bad"]["command_state"] == "confirmed"
    hass.states.async_set(lock, "off")  # the other automation is done: the deferred switch-off follows
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_src(False))
    assert log[-1] == ("turn_off", [X])
    await controller.async_stop()


# --- F3 --------------------------------------------------------------------------------------

async def test_f3_the_wording_follows_the_real_switch_off(hass, freezer) -> None:
    rooms = [_room("wasch", [X, Y], mode="recommendation")]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms, report=False)

    async def report(*fans_states):
        for fan, state in fans_states:
            hass.states.async_set(fan, state)
        await hass.async_block_till_done()

    await _tick(hass, freezer, coordinator, controller, 30, wasch=_rec("ventilate"))
    assert log == [("turn_on", [X, Y])]
    await report((X, "on"), (Y, "on"))
    await _tick(hass, freezer, coordinator, controller, 10, wasch=_rec("ventilate"))
    assert _view(controller, "wasch", [X, Y], aligned="ventilate", hass=hass)["fan_automation"]["state"] == "running"
    # the goal is reached: nothing is sent for 30 s – the text must not say the airing is being ended yet
    await _tick(hass, freezer, coordinator, controller, 10, wasch=_rec("close"))
    room = _view(controller, "wasch", [X, Y], hass=hass)
    value = room["fan_automation"]
    assert len(log) == 1 and value["command"] == "on" and value["command_state"] == "confirmed"
    assert value["state"] == "stopping" and value["label_key"] == "stop_check" and not value["user_action_needed"]
    assert value["label"] == "Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus"
    assert auto_stop(room) and fan_stop_message(room) == "Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus."
    await _tick(hass, freezer, coordinator, controller, 29, wasch=_rec("close"))  # 29 s after the goal was reached
    assert len(log) == 1 and _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]["label_key"] == "stop_check"
    await _tick(hass, freezer, coordinator, controller, 2, wasch=_rec("close"))   # 31 s: the switch-off is sent
    assert log[-1] == ("turn_off", [X, Y])
    value = _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]
    assert (value["state"], value["label_key"], value["command"], value["command_state"]) == ("stopping", "stopping", "off", "pending")
    # only one fan reports off so far: not finished
    await report((X, "off"))
    await _tick(hass, freezer, coordinator, controller, 10, wasch=_rec("close"))
    value = _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]
    assert value["state"] == "stopping" and value["command_state"] == "pending"
    await report((Y, "off"))
    await _tick(hass, freezer, coordinator, controller, 5, wasch=_rec("close"))
    value = _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]
    assert (value["state"], value["command_state"]) == ("completed", "confirmed") and not value["user_action_needed"]
    await controller.async_stop()


async def test_f3_an_unavailable_fan_is_never_shown_as_finished(hass, freezer) -> None:
    rooms = [_room("wasch", [X, Y], mode="recommendation")]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_rec("ventilate"))
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_rec("close"))
    hass.states.async_set(Y, "unavailable")
    await _tick(hass, freezer, coordinator, controller, 31, wasch=_rec("close"))
    assert log[-1] == ("turn_off", [X, Y])
    hass.states.async_set(Y, "unavailable")  # the service mock reported "off" – the device is gone again
    await _tick(hass, freezer, coordinator, controller, 5, wasch=_rec("close"))
    value = _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]
    assert value["state"] == "stopping" and value["fans_unknown"] == 1  # before: "completed" with one fan unknown
    await _tick(hass, freezer, coordinator, controller, 61, wasch=_rec("close"))
    value = _view(controller, "wasch", [X, Y], hass=hass)["fan_automation"]
    assert (value["state"], value["label_key"]) == ("failed", "failed_off") and value["user_action_needed"]
    await controller.async_stop()


# --- F4 --------------------------------------------------------------------------------------

async def test_f4_a_fan_that_did_not_come_on_is_asked_once_more(hass, freezer) -> None:
    freezer.move_to(START)
    log: list = []
    flaky = {"misses": 1}

    async def turn_on(call: ServiceCall) -> None:
        entities = sorted(call.data["entity_id"])
        log.append(("turn_on", entities))
        for fan in entities:
            if fan == Y and flaky["misses"]:
                flaky["misses"] -= 1
                continue  # the second fan does not react to the first command
            hass.states.async_set(fan, "on")

    async def turn_off(call: ServiceCall) -> None:
        log.append(("turn_off", sorted(call.data["entity_id"])))
        for fan in call.data["entity_id"]:
            hass.states.async_set(fan, "off")

    hass.services.async_register("homeassistant", "turn_on", turn_on)
    hass.services.async_register("homeassistant", "turn_off", turn_off)
    for fan in (X, Y):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("wasch", [X, Y], mode="recommendation")], entry_id="f4")
    await _tick(hass, freezer, coordinator, controller, 30, wasch=_rec("ventilate"))
    await _tick(hass, freezer, coordinator, controller, 61, wasch=_rec("ventilate"))  # timeout: only X is on
    assert log == [("turn_on", [X, Y]), ("turn_on", [X, Y])]  # before: Y was left off for the whole airing
    await _tick(hass, freezer, coordinator, controller, 5, wasch=_rec("ventilate"))
    snap = controller.fan_snapshot("wasch")
    assert snap["command_state"] == "confirmed" and snap["fans_on"] == 2
    await controller.async_stop()


async def test_f4_a_group_partly_switched_on_by_hand_is_not_taken_over(hass, freezer) -> None:
    rooms = [_room("wasch", [X, Y], mode="recommendation")]
    log, entry, coordinator, controller = await _setup(hass, freezer, rooms)
    hass.states.async_set(X, "on")  # switched on by hand
    for _ in range(4):
        await _tick(hass, freezer, coordinator, controller, 61, wasch=_rec("ventilate"))
    assert log == [] and not controller.fan_snapshot("wasch")["owned"]
    value = _view(controller, "wasch", [X, Y], aligned="ventilate", hass=hass)["fan_automation"]
    assert value["state"] == "manual" and value["group_incomplete"] and value["user_action_needed"]
    await controller.async_stop()
