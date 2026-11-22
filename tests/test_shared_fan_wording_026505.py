"""0.26.5.5 (community diagnosis): no "switch the fan off" while another room or automation runs it."""
from __future__ import annotations

import pytest

from custom_components.freshairiq.close_wording import fan_stop_message
from custom_components.freshairiq.fan_automation import AUTO_START_STATES, AUTO_STOP_STATES, room_fan_automation
from custom_components.freshairiq.notification_policy import auto_room_event

ROOM = {"key": "flur", "name": "Flur", "house_aligned_action": "close", "delta_g_m3": 1.2,
        "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": "switch.luefter", "mechanical_exhaust_active": True}}


@pytest.mark.parametrize(("snapshot", "state", "key"), [
    ({"shared_owner": True}, "shared", "shared_owner"),
    ({"owned": True, "shared_for": True}, "shared", "shared_for"),
    ({"external_lock": True}, "external", "external"),
    ({"external_lock": True, "owned": True}, "external", "external"),
])
def test_shared_and_external_fans_are_no_task_for_the_user(snapshot, state, key) -> None:
    automation = room_fan_automation(ROOM, snapshot)
    assert (automation["state"], automation["label_key"], automation["user_action_needed"]) == (state, key, False)
    room = {**ROOM, "fan_automation": automation}
    event, _title, text = auto_room_event("close", room, "Bitte Lüfter ausschalten")
    assert event == "fan_auto" and "ausschalten" not in text.lower()
    assert "ausschalten" not in fan_stop_message(room).lower()
    assert state in AUTO_STOP_STATES and state in AUTO_START_STATES


def test_an_own_running_room_and_a_hand_switched_fan_keep_their_states() -> None:
    assert room_fan_automation({**ROOM, "house_aligned_action": "continue_ventilating"}, {"owned": True, "shared_for": True})["state"] == "running"
    assert room_fan_automation(ROOM, {})["state"] == "manual"
    failed = room_fan_automation(ROOM, {"owned": True, "shared_for": True, "command": "off", "command_state": "failed"})
    assert failed["state"] == "failed"  # a failed switch-off is never hidden behind "shared"
    off = {**ROOM, "configured_actuators": {**ROOM["configured_actuators"], "mechanical_exhaust_active": False}}
    assert room_fan_automation(off, {"shared_owner": True})["state"] == "idle"


# ---------------------------------------------------------------------------------------- 0.26.7.2: support diagnosis 19./20.11.
# 19.11. 15:47 the office's switch-off at the maximum runtime failed (15:48 "failed"); both fans were off afterwards.
# 20.11. 07:26 the laundry room's control started the same fans – and the office showed the old "could not be switched off
# automatically" again. Replayed with FreshAirIQ's real fan control on the Home Assistant stub of the golden harness.
import asyncio  # noqa: E402
import itertools  # noqa: E402
import sys  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import coordinator_golden as golden  # noqa: E402,F401 – installs the Home Assistant stub of the golden harness
from golden import ha_stub  # noqa: E402

if not hasattr(sys.modules["homeassistant.core"], "Event"):
    sys.modules["homeassistant.core"].Event = object
if not hasattr(sys.modules["homeassistant.helpers.event"], "async_track_time_change"):
    sys.modules["homeassistant.helpers.event"].async_track_time_change = lambda *a, **k: (lambda: None)

from custom_components.freshairiq.actuator_controller import ActuatorController  # noqa: E402
from custom_components.freshairiq.fan_automation import automation_text  # noqa: E402

SHARED, OWN = "fan.bad_luefter", "fan.buro_luefter"
_ENTRIES = itertools.count()


def _house(office_fans, laundry_fans):
    hass = ha_stub.HomeAssistant()
    ha_stub.CLOCK.now = datetime(2026, 11, 19, 14, 47, 10, tzinfo=ha_stub.TZ)
    for fan in {*office_fans, *laundry_fans}:
        hass.states.async_set(fan, "off", {})
    rooms = [{"key": "buro", "name": "Büro", "exhaust_fan": office_fans, "exhaust_fan_control": "recommendation"},
             {"key": "waschkuche", "name": "Waschküche", "exhaust_fan": laundry_fans, "exhaust_fan_control": "recommendation"}]
    coordinator = SimpleNamespace(data={"rooms": {}}, options={}, async_add_listener=lambda f: (lambda: None))
    controller = ActuatorController(hass, coordinator, SimpleNamespace(entry_id=f"fan{next(_ENTRIES)}", data={"rooms": rooms}, options={}))
    asyncio.run(controller._async_attach())
    deaf: set[str] = set()   # devices that ignore a command
    calls = []
    original = hass.services.async_call

    async def call(domain, service, data=None, **kw):
        if domain == "homeassistant":
            calls.append((service, sorted(data["entity_id"])))
            for fan in data["entity_id"]:
                if fan not in deaf:
                    hass.states.async_set(fan, "on" if service == "turn_on" else "off", {})
        return await original(domain, service, data, **kw)

    hass.services.async_call = call
    return hass, controller, calls, deaf


def _cycle(controller, seconds, **aligned):
    ha_stub.CLOCK.advance(seconds)
    controller.coordinator.data = {"rooms": {key: {"house_aligned_action": action, "active": action in {"continue_ventilating", "close"},
                                                   "data_quality": "ok"}
                                             for key, action in aligned.items()}}
    asyncio.run(controller._async_evaluate(fans=True))


def _office(controller, hass, office_fans, aligned="wait"):
    on = any(hass.states.get(fan).state == "on" for fan in office_fans)
    room = {"key": "buro", "name": "Büro", "house_aligned_action": aligned,
            "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": office_fans, "mechanical_exhaust_active": on}}
    return room_fan_automation(room, controller.fan_snapshot("buro"))


def _failed_office_switch_off(office_fans, laundry_fans):
    """19.11.: the office starts its fans at 14:47, the switch-off at 15:47 (maximum runtime) is not carried out."""
    hass, controller, calls, deaf = _house(office_fans, laundry_fans)
    _cycle(controller, 0, buro="ventilate", waschkuche="wait")
    _cycle(controller, 10, buro="continue_ventilating", waschkuche="wait")
    deaf.update(office_fans)
    _cycle(controller, 3600, buro="continue_ventilating", waschkuche="wait")             # 15:47 maximum runtime
    _cycle(controller, 61, buro="continue_ventilating", waschkuche="wait")               # 15:48 not carried out
    assert controller.fan_snapshot("buro")["command_state"] == "failed"
    assert _office(controller, hass, office_fans)["label_key"] == "failed_off"
    deaf.clear()
    return hass, controller, calls, deaf


@pytest.mark.parametrize(("office_fans", "laundry_fans"), [
    ([SHARED, OWN], [SHARED, OWN]),     # the diagnosis: both rooms share both fans
    ([SHARED, OWN], [SHARED]),          # only part of the office's group is shared
])
def test_the_old_switch_off_warning_ends_once_every_fan_it_concerned_is_off(office_fans, laundry_fans) -> None:
    hass, controller, calls, _deaf = _failed_office_switch_off(office_fans, laundry_fans)
    for fan in office_fans:
        hass.states.async_set(fan, "off", {})                                            # switched off by hand afterwards
    _cycle(controller, 600, buro="wait", waschkuche="wait")
    assert controller.fan_snapshot("buro")["command_state"] == "confirmed"
    assert [(row["room_key"], row["command"], row["result"]) for row in controller.fan_trace()][-2:] == [
        ("buro", "off", "failed"), ("buro", "off", "confirmed")]                         # the failure stays in the trace
    # 20.11. 07:26: the laundry room starts the fans – no old warning in the office, the room that started them instead
    ha_stub.CLOCK.now = datetime(2026, 11, 20, 7, 26, 21, tzinfo=ha_stub.TZ)
    _cycle(controller, 0, buro="wait", waschkuche="ventilate_indirectly")
    _cycle(controller, 10, buro="continue_ventilating", waschkuche="continue_ventilating")
    assert calls[-1] == ("turn_on", sorted(laundry_fans))
    office = _office(controller, hass, office_fans, "continue_ventilating")
    assert (office["state"], office["label_key"], office["user_action_needed"]) == ("shared", "shared_owner", False)
    assert office["started_by"] == {"room_keys": ["waschkuche"], "room_names": ["Waschküche"]}
    assert automation_text(office) == "Gemeinsamer Ablüfter läuft – FreshAirIQ steuert ihn über einen anderen Raum"   # the cards name the room


@pytest.mark.parametrize("left", ["on", "unavailable"])
def test_a_fan_still_running_or_unreachable_keeps_the_switch_off_failed(left) -> None:
    hass, controller, _calls, _deaf = _failed_office_switch_off([SHARED, OWN], [SHARED])
    hass.states.async_set(SHARED, "off", {})
    hass.states.async_set(OWN, left, {})                                                 # the office's own fan
    _cycle(controller, 600, buro="wait", waschkuche="wait")
    assert controller.fan_snapshot("buro")["command_state"] == "failed"
    _cycle(controller, 600, buro="wait", waschkuche="ventilate_indirectly")              # the laundry room starts the shared fan
    office = _office(controller, hass, [SHARED, OWN])
    if left == "on":
        assert (office["state"], office["label_key"], office["user_action_needed"]) == ("failed", "failed_off", True)
    assert controller.fan_snapshot("buro")["command_state"] == "failed"


def test_a_new_failed_switch_off_is_shown_again() -> None:
    hass, controller, _calls, deaf = _failed_office_switch_off([SHARED, OWN], [SHARED, OWN])
    for fan in (SHARED, OWN):
        hass.states.async_set(fan, "off", {})
    _cycle(controller, 600, buro="wait", waschkuche="wait")
    assert controller.fan_snapshot("buro")["command_state"] == "confirmed"
    _cycle(controller, 60, buro="wait", waschkuche="wait")                              # the office's demand has ended
    _cycle(controller, 7200, buro="ventilate", waschkuche="wait")                       # a new run of the office …
    _cycle(controller, 10, buro="continue_ventilating", waschkuche="wait")
    deaf.update((SHARED, OWN))
    _cycle(controller, 3600, buro="continue_ventilating", waschkuche="wait")             # … whose switch-off fails again
    _cycle(controller, 61, buro="continue_ventilating", waschkuche="wait")
    office = _office(controller, hass, [SHARED, OWN], "continue_ventilating")
    assert (office["state"], office["label_key"], office["user_action_needed"]) == ("failed", "failed_off", True)
    assert controller.fan_trace()[-1]["result"] == "failed"


def test_several_starting_rooms_are_named_and_a_start_by_hand_names_none() -> None:
    hass, controller, calls, _deaf = _house([SHARED], [SHARED])
    controller.entry.data["rooms"].append({"key": "bad", "name": "Bad", "exhaust_fan": [SHARED, OWN], "exhaust_fan_control": "recommendation"})
    asyncio.run(controller.async_reload())
    hass.states.async_set(OWN, "off", {})
    hass.states.async_set(SHARED, "on", {})                                              # switched on by hand
    _cycle(controller, 0, buro="wait", waschkuche="wait", bad="wait")
    manual = _office(controller, hass, [SHARED])
    assert manual["state"] == "manual" and manual["started_by"] is None
    hass.states.async_set(SHARED, "off", {})
    _cycle(controller, 60, buro="wait", waschkuche="ventilate_indirectly", bad="ventilate_indirectly")
    _cycle(controller, 10, buro="continue_ventilating", waschkuche="continue_ventilating", bad="continue_ventilating")
    assert hass.states.get(SHARED).state == "on"
    started = _office(controller, hass, [SHARED], "continue_ventilating")["started_by"]
    owners = [key for key in ("waschkuche", "bad") if controller.fan_snapshot(key)["owned"]]
    names = {"waschkuche": "Waschküche", "bad": "Bad"}
    assert started == {"room_keys": owners, "room_names": [names[key] for key in owners]} and owners


def test_settling_a_failed_switch_off_names_only_proven_devices() -> None:
    from custom_components.freshairiq.fan_automation import settle_failed_off

    states = {"fan.a": "off", "fan.b": "on", "fan.c": "off"}
    all_off = lambda fans: all(states.get(fan) == "off" for fan in fans)  # noqa: E731
    sent = {"command": "off", "command_state": "failed", "off_targets": ["fan.a", "fan.b"]}
    assert settle_failed_off(sent, ["fan.a"], all_off) == [] and sent["command_state"] == "failed"   # B still runs
    older = {"command": "off", "command_state": "failed", "owned_fans": ["fan.a", "fan.c"]}          # from before the record
    assert settle_failed_off(older, ["fan.a", "fan.b", "fan.c"], all_off) == [older] and older["command_state"] == "confirmed"
    # the room's own fans next to a shared one (own_off): confirmed once they report off; nothing proven without devices
    own = {"command": "on", "command_state": "confirmed", "own_off": {"entities": ["fan.c"], "state": "failed"}}
    assert settle_failed_off(own, ["fan.c"], all_off) == [{"command": "off", "reason": "shared_fan_kept", "command_state": "confirmed"}]
    assert own["own_off"]["state"] == "confirmed"
    empty = {"own_off": {"entities": [], "state": "failed"}}
    assert settle_failed_off(empty, [], all_off) == [] and empty["own_off"]["state"] == "failed"
    running = {"own_off": {"entities": ["fan.b"], "state": "failed"}}
    assert settle_failed_off(running, ["fan.b"], all_off) == [] and running["own_off"]["state"] == "failed"


# ---------------------------------------------------------------------------------------- 0.26.7.2: support diagnosis 21.11. (Harald)
# The laundry room's fans stop at 09:38 (goal reached); at 10:18 its humidity sensor drops out ("check sensor"), then the
# readings are valid again with the unchanged demand; at 11:38 the repeat lock ends. Replayed on the real fan control.
def _room_cycle(controller, at, **rooms):
    ha_stub.CLOCK.now = at
    controller.coordinator.data = {"rooms": {key: dict(value) for key, value in rooms.items() if value is not None}}
    asyncio.run(controller._async_evaluate(fans=True))


def _valid(action, **extra):
    return {"house_aligned_action": action, "active": action in {"continue_ventilating", "close"}, "data_quality": "ok", **extra}


DROPOUTS = {
    "check_sensor": {"house_aligned_action": "check_sensor", "active": False, "data_quality": "error"},
    "missing_room_data": None,
    "invalid_readings": {"house_aligned_action": "wait", "active": False, "data_quality": "error"},
}


def _harald_house(dropout, end, *, office=None):
    hass, controller, calls, _deaf = _house([SHARED, OWN], [SHARED])
    at = lambda clock: datetime(2026, 11, 21, *(int(part) for part in clock.split(":")), tzinfo=ha_stub.TZ)  # noqa: E731
    idle = _valid("wait")
    _room_cycle(controller, at("09:32:28"), buro=idle, waschkuche=_valid("ventilate_indirectly"))
    _room_cycle(controller, at("09:32:38"), buro=idle, waschkuche=_valid("continue_ventilating"))
    _room_cycle(controller, at("09:37:41"), buro=idle, waschkuche=_valid("close"))
    _room_cycle(controller, at("09:38:11"), buro=idle, waschkuche=_valid("close"))
    _room_cycle(controller, at("09:38:21"), buro=idle, waschkuche=_valid("wait", repeat_cooldown_demoted=True))
    assert calls == [("turn_on", [SHARED]), ("turn_off", [SHARED])]
    assert controller.fan_snapshot("waschkuche")["await_new_demand"] is True
    _room_cycle(controller, at("10:18:00"), buro=idle, waschkuche=DROPOUTS[dropout])
    _room_cycle(controller, at("10:20:00"), buro=idle, waschkuche=DROPOUTS[dropout])
    for clock in ("10:24:00", "10:40:00", "11:20:00", "11:38:00"):
        _room_cycle(controller, at(clock), buro=idle, waschkuche=_valid("wait", repeat_cooldown_demoted=True))
    _room_cycle(controller, at("11:38:31"), buro=office or idle, waschkuche=end)
    return controller, calls[2:]


@pytest.mark.parametrize("dropout", list(DROPOUTS))
def test_harald_no_restart_after_a_sensor_dropout(dropout) -> None:
    controller, commands = _harald_house(dropout, _valid("ventilate_indirectly"))
    assert commands == []
    snapshot = controller.fan_snapshot("waschkuche")
    assert snapshot["reason"] == "demand_unchanged" and snapshot["await_new_demand"] is True


@pytest.mark.parametrize("end", [
    _valid("ventilate_indirectly", repeat_cooldown_override=True),     # a new reason that lifts the repeat lock
    _valid("ventilate_indirectly", moisture_source_active=True),       # urgent: a moisture source
    _valid("ventilate_indirectly", co2=1600, co2_available=True),      # urgent: critical CO2
], ids=["renewed", "moisture_source", "co2_critical"])
def test_harald_a_new_or_urgent_demand_still_starts(end) -> None:
    controller, commands = _harald_house("check_sensor", end)
    assert commands == [("turn_on", [SHARED])] and not controller.fan_snapshot("waschkuche")["await_new_demand"]


def test_harald_a_room_sharing_the_fan_still_starts_it() -> None:
    controller, commands = _harald_house("check_sensor", _valid("ventilate_indirectly"), office=_valid("ventilate"))
    assert commands == [("turn_on", sorted([SHARED, OWN]))]
    assert controller.fan_snapshot("buro")["owned"] and controller.fan_snapshot("waschkuche")["await_new_demand"]
