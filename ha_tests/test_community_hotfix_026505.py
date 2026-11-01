"""0.26.5.5 community hotfix (Simon42 #167/#170/#181): after the shower the exhaust fan keeps running
while the room's valid recommendation still says to air (moisture source recovery), and stops once it
no longer does – never longer than the recovery window, never against another automation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.fan_automation import room_fan_automation
from ha_tests.test_audit_026504c import _controller, _room, _services

START = datetime(2026, 10, 30, 7, 0, tzinfo=timezone.utc)
FAN = "switch.bad_luefter"


def _bad(**data):
    return {"moisture_source_active": False, "moisture_source_recovery": False, "house_aligned_action": "close",
            "configured_actuators": {"window_open": False}, **data}


async def _tick(hass, freezer, coordinator, controller, minutes, **rooms):
    freezer.tick(timedelta(minutes=minutes))
    coordinator.data = {"rooms": rooms}
    await controller._async_evaluate(fans=True)
    await hass.async_block_till_done()


async def test_the_fan_runs_on_while_the_recommendation_still_says_air_after_the_shower(hass, freezer) -> None:
    freezer.move_to(START)
    log = _services(hass)
    hass.states.async_set(FAN, "off")
    _entry, coordinator, controller = await _controller(hass, [{**_room("bad", [FAN]), "exhaust_fan_follow_up_min": 10}], entry_id="a")
    await _tick(hass, freezer, coordinator, controller, 0.5, bad=_bad(moisture_source_active=True, house_aligned_action="continue_ventilating"))
    assert log == [("turn_on", [FAN])]
    # the shower ended; the room is still humid and the recommendation says to keep airing
    for _ in range(12):
        await _tick(hass, freezer, coordinator, controller, 1, bad=_bad(moisture_source_recovery=True, house_aligned_action="continue_ventilating"))
    assert log == [("turn_on", [FAN])] and hass.states.get(FAN).state == "on"  # before: off after the 10-minute follow-up
    snap = controller.fan_snapshot("bad")
    room = {"configured_actuators": {"exhaust_fan_control": "moisture_source", "exhaust_fan": [FAN], "mechanical_exhaust_active": True},
            "house_aligned_action": "continue_ventilating"}
    assert room_fan_automation(room, snap)["state"] == "follow_up" and not room_fan_automation(room, snap)["user_action_needed"]
    # the recommendation turns to close: the follow-up (long over) no longer holds the fan
    await _tick(hass, freezer, coordinator, controller, 1, bad=_bad(moisture_source_recovery=True))
    assert log[-1] == ("turn_off", [FAN])
    await controller.async_stop()


async def test_without_the_recommendation_or_after_the_recovery_window_the_follow_up_applies(hass, freezer) -> None:
    freezer.move_to(START)
    log = _services(hass)
    hass.states.async_set(FAN, "off")
    _entry, coordinator, controller = await _controller(hass, [{**_room("bad", [FAN]), "exhaust_fan_follow_up_min": 10}], entry_id="b")
    await _tick(hass, freezer, coordinator, controller, 0.5, bad=_bad(moisture_source_active=True))
    for _ in range(11):  # recovery, but the recommendation says close: the plain follow-up ends it
        await _tick(hass, freezer, coordinator, controller, 1, bad=_bad(moisture_source_recovery=True))
    assert log[-1] == ("turn_off", [FAN])
    # recovery window over (moisture_source_recovery False) – a continuing recommendation alone does not hold it
    await _tick(hass, freezer, coordinator, controller, 1, bad=_bad(moisture_source_active=True, house_aligned_action="continue_ventilating"))
    for _ in range(11):
        await _tick(hass, freezer, coordinator, controller, 1, bad=_bad(house_aligned_action="continue_ventilating"))
    assert log[-1] == ("turn_off", [FAN])
    await controller.async_stop()


# --- GitHub #15: no house "ventilate" push right after a house "close" push ------------------

async def test_github_15_house_push_does_not_say_open_right_after_close(hass) -> None:
    from pytest_homeassistant_custom_component.common import async_mock_service
    from custom_components.freshairiq.notifications import process_notifications
    from ha_tests.test_cov_notifications import NOW, Store, _options

    calls = async_mock_service(hass, "notify", "phone")
    options = _options(notification_scope="house", notification_cooldown_min=30, repeat_recommendation_cooldown_min=120)
    store = Store()
    small = {"key": "bad", "name": "Bad", "action": "Close", "data_quality": "ok", "mould_level": "Low", "surface_rh": 70}

    async def push(at, kind, instruction, room=small):
        data = {"rooms": {"bad": room}, "intelligent_recommendation": {"kind": kind, "room_keys": ["bad"], "instruction": instruction}}
        await process_notifications(hass, store, data, options, at, [])
        await hass.async_block_till_done()

    await push(NOW, "close", "Bad schließen.")
    assert len(calls) == 1
    # humidity rises again in the 9.4 m³ bathroom 35 minutes later: the open push waits (before: sent – the
    # "close" and "open" pushes have separate cooldowns)
    await push(NOW + timedelta(minutes=35), "ventilate", "Bad lüften.", {**small, "action": "Ventilate"})
    assert len(calls) == 1
    # protection (critical mould risk) is never held back
    await push(NOW + timedelta(minutes=40), "ventilate", "Bad lüften!", {**small, "action": "Ventilate", "surface_rh": 92})
    assert len(calls) == 2
    # without protection, the held recommendation follows once the repeat cooldown is over
    store2 = Store()
    store, store2 = store2, store
    await push(NOW, "close", "Bad schließen.")
    await push(NOW + timedelta(minutes=35), "ventilate", "Bad lüften.", {**small, "action": "Ventilate"})
    assert len(calls) == 3
    await push(NOW + timedelta(minutes=121), "ventilate", "Bad lüften.", {**small, "action": "Ventilate"})
    assert len(calls) == 4 and "Bad lüften" in calls[-1].data["message"]
