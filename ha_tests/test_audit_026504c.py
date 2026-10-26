"""0.26.5.4: consolidated audit of the 0.26.5.4 artefact, in a real Home Assistant.

S02  "off + unavailable" is no confirmed switch-off.
S03  room A runs [shared, private], room B needs only "shared": when A is done,
     its private fan is switched off, the shared one stays on for B.
S05  switching A's fan control off does not switch off a fan B still needs; it is
     switched off once B no longer needs it.
S11  a switch-off still pending before a restart is followed although no room is
     controlled any more.
S04  a short CO2 sensor outage does not end the CO2 hold band.
"""
from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freshairiq.actuator_controller import ActuatorController
from custom_components.freshairiq.const import DOMAIN
from ha_tests import test_cov_options_flow as opt
from ha_tests.test_cov_coordinator_b import CO2, HUM, OPTIONS, _cleanup_coordinators, _make  # noqa: F401

SHARED, PRIVATE = "switch.shared_fan", "switch.private_fan"


def _room(key: str, fans: list[str], mode: str = "moisture_source") -> dict:
    return {**opt._room(key.title(), key=key), "exhaust_fan": fans, "exhaust_fan_control": mode,
            "exhaust_fan_follow_up_min": 0, "exhaust_fan_max_runtime_min": 240}


def _services(hass, *, report: bool = True) -> list:
    log: list = []

    def handler(service: str):
        async def run(call: ServiceCall) -> None:
            entities = call.data["entity_id"]
            entities = [entities] if isinstance(entities, str) else list(entities)
            log.append((service, sorted(entities)))
            if report:
                for entity_id in entities:
                    hass.states.async_set(entity_id, "on" if service == "turn_on" else "off")
        return run
    for service in ("turn_on", "turn_off"):
        hass.services.async_register("homeassistant", service, handler(service))
    return log


async def _controller(hass, rooms: list[dict], entry_id: str = "audit"):
    entry = MockConfigEntry(domain=DOMAIN, entry_id=entry_id, data={"rooms": rooms, "levels": ["EG"]})
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(data={"rooms": {}}, options={}, async_add_listener=lambda cb: (lambda: None))
    controller = ActuatorController(hass, coordinator, entry)
    await controller.async_start()
    return entry, coordinator, controller


async def _cycle(hass, coordinator, controller, **sources: bool) -> None:
    coordinator.data = {"rooms": {key: {"moisture_source_active": active} for key, active in sources.items()}}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def test_a_shared_fan_stays_for_the_other_room_the_private_one_goes_off(hass) -> None:
    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=False)
    assert log == [("turn_on", [PRIVATE, SHARED])]
    await _cycle(hass, coordinator, controller, a=False, b=True)  # A is done, B needs the shared fan
    assert log[-1] == ("turn_off", [PRIVATE]) and hass.states.get(SHARED).state == "on"
    assert controller.fan_trace()[-1]["reason"] == "shared_fan_kept"
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert len(log) == 2  # nothing repeated
    await _cycle(hass, coordinator, controller, a=False, b=False)  # nobody needs it: A switches its group off
    assert log[-1] == ("turn_off", [PRIVATE, SHARED]) and hass.states.get(SHARED).state == "off"
    await controller.async_stop()


async def test_off_plus_unavailable_is_not_confirmed(hass) -> None:
    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE])])
    await _cycle(hass, coordinator, controller, a=True)
    await _cycle(hass, coordinator, controller, a=True)  # both report on: the start is confirmed
    log = _services(hass, report=False)  # from now on the devices do not report back
    await _cycle(hass, coordinator, controller, a=False)
    assert log[-1] == ("turn_off", [PRIVATE, SHARED]) and controller.fan_snapshot("a")["command_state"] == "pending"
    hass.states.async_set(PRIVATE, "unavailable")
    hass.states.async_set(SHARED, "off")  # one fan reports off, the other cannot be reached
    await _cycle(hass, coordinator, controller, a=False)
    snapshot = controller.fan_snapshot("a")
    assert snapshot["command"] == "off" and snapshot["command_state"] == "pending"
    hass.states.async_set(PRIVATE, "off")
    await _cycle(hass, coordinator, controller, a=False)
    assert controller.fan_snapshot("a")["command_state"] == "confirmed"
    await controller.async_stop()


async def test_removing_the_control_keeps_a_fan_the_other_room_needs(hass) -> None:
    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=True)
    assert log == [("turn_on", [PRIVATE, SHARED])]
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("a", [SHARED, PRIVATE], mode="off"), _room("b", [SHARED])]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert log[-1] == ("turn_off", [PRIVATE]) and hass.states.get(SHARED).state == "on"
    # audit N02: the private fan reported off - settled at once, the shared one still waits for B
    assert controller.fan_snapshot("a")["command_state"] == "confirmed"
    await _cycle(hass, coordinator, controller, a=False, b=False)  # B no longer needs it
    assert ("turn_off", [SHARED]) in log and hass.states.get(SHARED).state == "off"
    await _cycle(hass, coordinator, controller, a=False, b=False)
    assert controller.fan_snapshot("a")["command_state"] == "confirmed"
    assert [row["result"] for row in controller.fan_trace()][-1] == "confirmed"
    await controller.async_stop()


async def test_a_pending_switch_off_is_followed_after_a_restart_without_controlled_rooms(hass) -> None:
    _services(hass)
    hass.states.async_set(PRIVATE, "off")
    entry, coordinator, controller = await _controller(hass, [_room("a", [PRIVATE])], entry_id="restart")
    await _cycle(hass, coordinator, controller, a=True)
    _services(hass, report=False)  # the device does not report the switch-off before the restart
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("a", [PRIVATE], mode="off")]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert controller.fan_snapshot("a")["command_state"] == "pending"
    await controller.async_stop()  # Home Assistant restarts before the device reported
    restarted = ActuatorController(hass, coordinator, entry)
    await restarted.async_start()
    await restarted._async_update()  # first coordinator update after the start
    assert restarted.fan_snapshot("a")["command_state"] == "pending"  # the stored state was loaded
    hass.states.async_set(PRIVATE, "off")
    await restarted._async_update()
    assert restarted.fan_snapshot("a")["command_state"] == "confirmed"
    await restarted.async_stop()


async def test_a_short_co2_outage_keeps_the_hold_band(hass, freezer) -> None:
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400})
    for _ in range(3):
        await d.step(60)
    await d.step(60, binary_sensor__kueche_fenster="on")
    await d.step(60, sensor__kueche_co2=(1100, CO2), sensor__kueche_h=(60.8, HUM))
    assert d.mem("kueche")["co2_lead_latched"] is True
    await d.step(60, sensor__kueche_co2=("unavailable", CO2), sensor__kueche_h=(60.6, HUM))
    assert d.mem("kueche")["co2_lead_latched"] is True  # no value is not "below the band"
    for i, co2 in enumerate((975, 960)):
        await d.step(60, sensor__kueche_co2=(co2, CO2), sensor__kueche_h=(round(60.4 - 0.1 * i, 1), HUM))
        assert d.mem("kueche")["co2_lead_latched"] is True and d.room("kueche")["action"] == "Continue ventilating"
    await d.step(60, sensor__kueche_co2=(949, CO2), sensor__kueche_h=(60.1, HUM))
    assert d.mem("kueche")["co2_lead_latched"] is False  # a valid reading below the band ends it


async def test_in_the_recommendation_mode_the_private_fan_waits_for_the_off_confirmation(hass, freezer) -> None:
    from datetime import timedelta

    from custom_components.freshairiq.actuator_control import FAN_OFF_CONFIRM_S

    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE], mode="recommendation"), _room("b", [SHARED])])

    async def cycle(a: str, b: bool) -> None:
        coordinator.data = {"rooms": {"a": {"house_aligned_action": a, "configured_actuators": {}},
                                      "b": {"moisture_source_active": b}}}
        await controller._async_evaluate(fans=True)
        await hass.async_block_till_done()

    await cycle("ventilate", False)
    assert log == [("turn_on", [PRIVATE, SHARED])]
    await cycle("close", True)  # A is done, B needs the shared fan: first the off confirmation
    assert len(log) == 1
    freezer.tick(timedelta(seconds=FAN_OFF_CONFIRM_S + 1))
    await cycle("close", True)
    assert log[-1] == ("turn_off", [PRIVATE]) and hass.states.get(SHARED).state == "on"
    await controller.async_stop()


# --------------------------------------------------------------------------- audit of the 0.26.5.4(4) artefact

async def test_n01_the_own_fan_switch_off_is_followed_once_and_fails_visibly(hass, freezer) -> None:
    from datetime import timedelta

    from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S

    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=False)
    log = _services(hass, report=False)  # the private fan accepts the service call but never goes off
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert log == [("turn_off", [PRIVATE])] and controller.fan_snapshot("a")["own_off"] == "pending"
    for seconds in (31, 31):  # the off confirmation of the recommendation mode would have passed twice
        freezer.tick(timedelta(seconds=seconds))
        await _cycle(hass, coordinator, controller, a=False, b=True)
    assert log == [("turn_off", [PRIVATE])]  # no repeated commands
    assert controller.fan_snapshot("a")["own_off"] == "failed" and hass.states.get(SHARED).state == "on"
    rows = [(r["reason"], r["result"]) for r in controller.fan_trace()]
    assert rows[-2:] == [("shared_fan_kept", "pending"), ("shared_fan_kept", "failed")]
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S))
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert len(controller.fan_trace()) == len(rows)  # settled once
    await controller.async_stop()


async def test_n01_a_reported_own_fan_switch_off_is_confirmed(hass) -> None:
    _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=False)
    await _cycle(hass, coordinator, controller, a=False, b=True)
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert controller.fan_snapshot("a")["own_off"] == "confirmed"
    await _cycle(hass, coordinator, controller, a=True, b=True)  # A needs its group again: decided as a whole
    assert controller.fan_snapshot("a")["own_off"] is None
    await controller.async_stop()


async def test_n02_the_private_switch_off_settles_while_the_shared_fan_still_waits(hass, freezer) -> None:
    from datetime import timedelta

    from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S

    log = _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=True)
    log = _services(hass, report=False)  # nothing reports back any more
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("a", [SHARED, PRIVATE], mode="off"), _room("b", [SHARED])]})
    await controller.async_reload()
    await hass.async_block_till_done()
    assert log == [("turn_off", [PRIVATE])] and controller.fan_snapshot("a")["command_state"] == "pending"
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1))
    await _cycle(hass, coordinator, controller, a=False, b=True)  # B needs the shared fan for hours
    assert controller.fan_snapshot("a")["command_state"] == "failed" and hass.states.get(SHARED).state == "on"
    assert controller.fan_trace()[-1]["result"] == "failed"
    await _cycle(hass, coordinator, controller, a=False, b=False)  # B is done: the shared fan is switched off now
    assert log[-1] == ("turn_off", [SHARED]) and controller.fan_snapshot("a")["command_state"] == "pending"
    hass.states.async_set(SHARED, "off")
    await _cycle(hass, coordinator, controller, a=False, b=False)
    # audit F02: the private fan never went off – the whole switch-off stays "failed"
    assert controller.fan_snapshot("a")["command_state"] == "failed"
    await controller.async_stop()


async def test_n02_only_a_shared_fan_left_waits_without_a_timeout(hass, freezer) -> None:
    from datetime import timedelta

    log = _services(hass)
    hass.states.async_set(SHARED, "off")
    entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=True)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("a", [SHARED], mode="off"), _room("b", [SHARED])]})
    await controller.async_reload()
    await hass.async_block_till_done()
    freezer.tick(timedelta(hours=2))
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert controller.fan_snapshot("a")["command_state"] == "waiting" and log == [("turn_on", [SHARED])]
    await controller.async_stop()


# --------------------------------------------------------------------------- audit of the 0.26.5.4(5) artefact

async def test_f01_the_own_fan_result_is_saved(hass, freezer) -> None:
    from datetime import timedelta
    from unittest.mock import MagicMock

    from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S

    _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    _entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=False)
    _services(hass, report=False)
    await _cycle(hass, coordinator, controller, a=False, b=True)  # own switch-off sent, pending
    controller._store.async_delay_save = MagicMock()
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1))
    room_a = next(room for room in controller._rooms if room["key"] == "a")
    # only room A's own result changes (room B alone would also trigger a save, so A is asked directly)
    changed = await controller._async_fans(room_a, {"moisture_source_active": False}, needed_elsewhere={SHARED})
    assert changed is True and controller.fan_snapshot("a")["own_off"] == "failed"
    await _cycle(hass, coordinator, controller, a=False, b=True)
    controller._store.async_delay_save.assert_called()  # the result and its trace row are saved
    await controller.async_stop()


async def test_f02_a_failed_part_stays_failed_when_the_shared_fan_goes_off_later(hass, freezer) -> None:
    from datetime import timedelta

    from custom_components.freshairiq.actuator_control import FAN_COMMAND_TIMEOUT_S

    _services(hass)
    for fan in (SHARED, PRIVATE):
        hass.states.async_set(fan, "off")
    entry, coordinator, controller = await _controller(hass, [_room("a", [SHARED, PRIVATE]), _room("b", [SHARED])])
    await _cycle(hass, coordinator, controller, a=True, b=True)
    log = _services(hass, report=False)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "rooms": [_room("a", [SHARED, PRIVATE], mode="off"), _room("b", [SHARED])]})
    await controller.async_reload()
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=FAN_COMMAND_TIMEOUT_S + 1))
    await _cycle(hass, coordinator, controller, a=False, b=True)
    assert controller.fan_snapshot("a")["command_state"] == "failed"  # the private fan did not go off
    await _cycle(hass, coordinator, controller, a=False, b=False)  # B is done: the shared fan is switched off
    assert log[-1] == ("turn_off", [SHARED])
    hass.states.async_set(SHARED, "off")
    await _cycle(hass, coordinator, controller, a=False, b=False)
    assert controller.fan_snapshot("a")["command_state"] == "failed"  # not "confirmed": the private fan still runs
    hass.states.async_set(PRIVATE, "off")  # it reports off later after all
    await _cycle(hass, coordinator, controller, a=False, b=False)
    assert controller.fan_snapshot("a")["command_state"] == "confirmed"
    assert controller.fan_trace()[-1]["result"] == "confirmed"
    await controller.async_stop()
