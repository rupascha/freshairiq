"""0.26.5.4 hotfix: automatic exhaust-fan control without feedback, honest messages.

Support diagnosis 24.10. (garage): 13:30:54 close + push "iq_close", 13:31:24
continue, 13:31:25 close again, 13:31:35 session ended – and in the Home
Assistant history the fan ON at 13:31:24 and OFF at 13:31:25. Switching the fan
changes the very evaluation that switched it (a running fan is an airing session
with its own close checks); the controller switched off at the first "close"
and on again at the next "ventilate/continue".

Pure parts: the fan decision (switch-off confirmation, restart pause after a
finished airing, pending/failed commands), the derived automation state and the
wording of instructions, events and notifications.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.actuator_control import (
    FAN_COMMAND_TIMEOUT_S,
    FAN_CONTROL_MOISTURE_SOURCE,
    FAN_CONTROL_OFF,
    FAN_CONTROL_RECOMMENDATION,
    FAN_OFF_CONFIRM_S,
    decide_fan,
    fan_demand,
)
from custom_components.freshairiq.automation_events import recommendation_payload, room_payload
from custom_components.freshairiq.close_wording import (
    area_close_instruction,
    close_instruction,
    fan_stop_message,
    house_handled_by_automation,
    keep_instruction,
)
from custom_components.freshairiq.exhaust_reference import exhaust_reference_applies
from custom_components.freshairiq.fan_automation import (
    auto_start,
    auto_stop,
    automation_label,
    event_fields,
    fan_restart_lock_min,
    fan_trace_row,
    handled_label,
    room_fan_automation,
)
from custom_components.freshairiq.localize import to_english
from custom_components.freshairiq.notification_policy import auto_house, auto_room_event, room_notification_events

T0 = datetime(2026, 10, 24, 13, 30, 54, tzinfo=timezone.utc)
LOCK = 15.0


def _decide(mem, *, fan_on, demand, seconds, mode=FAN_CONTROL_RECOMMENDATION, **extra):
    params = dict(off_confirm_s=FAN_OFF_CONFIRM_S, restart_lock_min=LOCK) if mode == FAN_CONTROL_RECOMMENDATION else {}
    params.update(extra)
    return decide_fan(mode=mode, fan_on=fan_on, demand=demand, now=T0 + timedelta(seconds=seconds),
                      follow_up_min=10, max_runtime_min=60, mem=mem, **params)


def _started(mem) -> None:
    assert _decide(mem, fan_on=False, demand=True, seconds=0) == "on"
    assert _decide(mem, fan_on=True, demand=True, seconds=5) is None
    assert mem["command_state"] == "confirmed" and mem["owned"] is True


# --------------------------------------------------------------------------- the switching logic
def test_garage_sequence_close_continue_close_causes_no_switching_cycle() -> None:
    mem: dict = {}
    _started(mem)
    # 13:30:54 close, 13:31:24 continue, 13:31:25 close – the fan just keeps running
    assert _decide(mem, fan_on=True, demand=False, seconds=600) is None
    assert mem["reason"] == "off_confirming"
    assert _decide(mem, fan_on=True, demand=True, seconds=630) is None
    assert "off_pending_since" not in mem
    assert _decide(mem, fan_on=True, demand=False, seconds=631) is None
    assert _decide(mem, fan_on=True, demand=True, seconds=631.5) is None
    assert mem["owned"] is True and mem["command"] == "on"


def test_a_stable_close_ends_the_airing_and_the_fan_does_not_restart_at_once() -> None:
    mem: dict = {}
    _started(mem)
    assert _decide(mem, fan_on=True, demand=False, seconds=600) is None
    assert _decide(mem, fan_on=True, demand=False, seconds=600 + FAN_OFF_CONFIRM_S) == "off"
    assert (mem["reason"], mem["owned"], mem["command_state"]) == ("goal_reached", False, "pending")
    assert _decide(mem, fan_on=False, demand=False, seconds=640) is None and mem["command_state"] == "confirmed"
    # the evaluation without a running fan says "ventilate" again: no restart within the pause
    assert _decide(mem, fan_on=False, demand=True, seconds=660) is None and mem["reason"] == "restart_locked"
    assert _decide(mem, fan_on=False, demand=True, seconds=630 + LOCK * 60 - 1) is None
    assert _decide(mem, fan_on=False, demand=True, seconds=630 + LOCK * 60) == "on"


def test_urgent_need_skips_the_restart_pause() -> None:
    mem: dict = {}
    _started(mem)
    _decide(mem, fan_on=True, demand=False, seconds=600)
    _decide(mem, fan_on=True, demand=False, seconds=640)
    _decide(mem, fan_on=False, demand=False, seconds=645)
    assert _decide(mem, fan_on=False, demand=True, seconds=700, urgent=True) == "on"


def test_moisture_coming_in_maximum_runtime_and_control_off_stop_at_once() -> None:
    mem: dict = {}
    _started(mem)
    assert _decide(mem, fan_on=True, demand=False, seconds=100, safety_off=True) == "off"
    assert mem["reason"] == "moisture_ingress"
    mem = {}
    _started(mem)
    assert _decide(mem, fan_on=True, demand=True, seconds=3600) == "off" and mem["reason"] == "max_runtime"
    assert mem["blocked"] is True  # not switched on again while the demand lasts
    assert _decide(mem, fan_on=False, demand=True, seconds=3610) is None
    mem = {}
    _started(mem)
    assert _decide(mem, fan_on=True, demand=True, seconds=100, mode=FAN_CONTROL_OFF) == "off"
    assert mem["reason"] == "control_off"


def test_a_switched_off_fan_stays_off_and_a_hand_started_fan_is_left_alone() -> None:
    mem: dict = {}
    _started(mem)
    _decide(mem, fan_on=True, demand=False, seconds=100)  # confirming a switch-off …
    assert _decide(mem, fan_on=False, demand=True, seconds=110) is None  # … and switched off by hand
    assert (mem["reason"], mem["blocked"], mem["owned"]) == ("manual_off", True, False)
    assert _decide(mem, fan_on=False, demand=True, seconds=200) is None
    # one flicker of the recommendation does not count as "the demand has ended"
    assert _decide(mem, fan_on=False, demand=False, seconds=201) is None and mem["blocked"] is True
    assert _decide(mem, fan_on=False, demand=True, seconds=202) is None and mem["blocked"] is True
    assert _decide(mem, fan_on=False, demand=False, seconds=300) is None
    assert _decide(mem, fan_on=False, demand=False, seconds=300 + FAN_OFF_CONFIRM_S) is None and mem["blocked"] is False
    # started by hand: never switched off by FreshAirIQ
    mem = {}
    assert _decide(mem, fan_on=True, demand=True, seconds=0) is None
    assert _decide(mem, fan_on=True, demand=False, seconds=600) is None and not mem.get("owned")


def test_a_late_state_report_is_no_manual_switch_and_a_lost_command_fails() -> None:
    mem: dict = {}
    assert _decide(mem, fan_on=False, demand=True, seconds=0) == "on"
    # Home Assistant has not reported "on" yet: still ours, not "switched off by hand"
    assert _decide(mem, fan_on=False, demand=True, seconds=2) is None
    assert (mem["owned"], mem["command_state"]) == (True, "pending")
    assert _decide(mem, fan_on=False, demand=True, seconds=FAN_COMMAND_TIMEOUT_S) is None
    assert (mem["owned"], mem["command_state"], mem["reason"], mem["blocked"]) == (False, "failed", "command_failed", True)
    # a switch-off that is never carried out
    mem = {}
    _started(mem)
    _decide(mem, fan_on=True, demand=False, seconds=100, safety_off=True)
    assert _decide(mem, fan_on=True, demand=False, seconds=110) is None and mem["command_state"] == "pending"
    assert _decide(mem, fan_on=True, demand=False, seconds=100 + FAN_COMMAND_TIMEOUT_S) is None
    assert mem["command_state"] == "failed"


def test_moisture_source_mode_ignores_the_recommendation_and_keeps_its_follow_up() -> None:
    assert fan_demand(FAN_CONTROL_MOISTURE_SOURCE, source_active=True, recommendation="close", window_open=False)
    assert not fan_demand(FAN_CONTROL_MOISTURE_SOURCE, source_active=False, recommendation="continue_ventilating", window_open=False)
    mem: dict = {}
    m = FAN_CONTROL_MOISTURE_SOURCE
    assert _decide(mem, fan_on=False, demand=True, seconds=0, mode=m) == "on"
    assert _decide(mem, fan_on=True, demand=False, seconds=60, mode=m) is None and mem["reason"] == "follow_up"
    assert _decide(mem, fan_on=True, demand=False, seconds=599, mode=m) is None
    assert _decide(mem, fan_on=True, demand=False, seconds=601, mode=m) == "off" and mem["reason"] == "follow_up_ended"
    assert _decide(mem, fan_on=False, demand=True, seconds=605, mode=m) == "on"  # no restart pause for a new source


def test_restart_pause_follows_the_existing_anti_flap_floor() -> None:
    assert fan_restart_lock_min({}) == 15.0
    assert fan_restart_lock_min({"repeat_recommendation_cooldown_min": 10}) == 10.0
    assert fan_restart_lock_min({"post_ventilation_stabilization_min": 20}) == 20.0
    assert fan_restart_lock_min({"post_ventilation_stabilization_min": "x"}) == 15.0
    row = fan_trace_row("garage", "recommendation", {"command": "on", "reason": "recommendation", "command_state": "pending"}, T0)
    assert row == {"at": T0.isoformat(), "room_key": "garage", "mode": "recommendation", "command": "on",
                   "reason": "recommendation", "result": "pending"}


# --------------------------------------------------------------------------- the automation state
def _room(*, mode="recommendation", fan_on=False, window=False, aligned="ventilate", source=False, **extra) -> dict:
    room = {"key": "garage", "name": "Garage", "house_aligned_action": aligned, "moisture_source_active": source,
            "configured_actuators": {"exhaust_fan": "switch.garage", "exhaust_fan_control": mode,
                                     "mechanical_exhaust_active": fan_on, "window_open": window}}
    room.update(extra)
    return room


@pytest.mark.parametrize(("room", "snap", "state", "label"), [
    (_room(), {}, "recommended", "Automatische Lüftung empfohlen – Ablüfter wird automatisch eingeschaltet"),
    (_room(), {"owned": True, "command": "on", "command_state": "pending"}, "requested", "Ablüfter wird automatisch eingeschaltet"),
    (_room(fan_on=True, aligned="continue_ventilating"), {"owned": True, "command": "on", "command_state": "confirmed"}, "running", "Automatische Lüftung läuft"),
    (_room(fan_on=True, aligned="close"), {"owned": True, "command": "on", "command_state": "confirmed"}, "stopping", "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung"),
    (_room(fan_on=True, mode="moisture_source", source=True, aligned="close"), {"owned": True}, "source", "Ablüfter läuft wegen erkannter Feuchtequelle"),
    (_room(fan_on=True, mode="moisture_source", aligned="close"), {"owned": True}, "follow_up", "Feuchtequelle beendet – automatische Nachlaufzeit aktiv"),
    (_room(fan_on=True, aligned="close"), {}, "manual", None),
    (_room(), {"blocked": True}, "manual_off", None),
    (_room(), {"restart_locked": True}, "waiting", "Automatische Lüftung startet nach der Pause"),
    (_room(source=True), {"restart_locked": True}, "recommended", "Automatische Lüftung empfohlen – Ablüfter wird automatisch eingeschaltet"),
    (_room(), {"command": "on", "command_state": "failed"}, "failed", "Ablüfter konnte nicht automatisch eingeschaltet werden – bitte von Hand einschalten"),
    (_room(fan_on=True, aligned="close"), {"command": "off", "command_state": "failed"}, "failed", "Ablüfter konnte nicht automatisch ausgeschaltet werden – bitte von Hand ausschalten"),
    (_room(aligned="okay"), {"command": "off", "command_state": "confirmed"}, "completed", None),
    (_room(aligned="okay"), {}, "idle", None),
    (_room(window=True), {}, "idle", None),
    (_room(mode="moisture_source"), {}, "idle", None),
])
def test_automation_state(room, snap, state, label) -> None:
    value = room_fan_automation(room, snap)
    assert (value["state"], value["label"]) == (state, label)
    assert value["user_action_needed"] is (state in {"failed", "manual", "manual_off"})
    assert set(event_fields({"fan_automation": value})) == {"mode", "state", "owned", "command", "command_state", "user_action_needed"}


def test_no_automation_without_mode_or_fan() -> None:
    assert room_fan_automation(_room(mode="off"), {}) is None
    room = _room()
    room["configured_actuators"]["exhaust_fan"] = None
    assert room_fan_automation(room, None) is None
    assert event_fields({}) is None and automation_label({}) is None and not auto_stop("x") and not auto_start(None)


def _with(room: dict, snap: dict) -> dict:
    room["fan_automation"] = room_fan_automation(room, snap)
    return room


OWNED = {"owned": True, "command": "on", "command_state": "confirmed"}


# --------------------------------------------------------------------------- wording
def test_close_instruction_names_only_what_the_user_has_to_do() -> None:
    auto = _with(_room(fan_on=True, aligned="close", close_recommended=True), OWNED)
    manual = _with(_room(fan_on=True, aligned="close", close_recommended=True, key="bad", name="Bad"), {})
    window = {"key": "wohn", "name": "Wohnzimmer", "configured_actuators": {"window_open": True}}
    assert close_instruction([auto]) == "FreshAirIQ beendet die automatische Lüftung in Garage"
    assert close_instruction([manual]) == "Lüfter in Bad ausschalten"
    assert close_instruction([window, manual, auto]) == "Wohnzimmer schließen · Lüfter in Bad ausschalten · FreshAirIQ beendet die automatische Lüftung in Garage"
    assert area_close_instruction("Erdgeschoss", [window, auto]) == "Erdgeschoss schließen"
    assert area_close_instruction("Erdgeschoss", [window, manual]) == "Erdgeschoss schließen · Lüfter in Bad ausschalten"
    running = _with(_room(fan_on=True, aligned="continue_ventilating"), OWNED)
    assert keep_instruction([running], 4) == "Automatische Lüftung in Garage läuft · noch ca. 4 min"
    assert keep_instruction([window, manual], None) == "Wohnzimmer offen lassen · Lüfter in Bad laufen lassen"


def test_fan_stop_message_by_cause_air_path_and_command_result() -> None:
    assert fan_stop_message(_with(_room(fan_on=True, aligned="close"), OWNED)) == "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung."
    manual = _room(fan_on=True, aligned="close", delta_g_m3=-0.5)
    assert fan_stop_message(manual) == "Die Außenluft ist gerade feuchter als die Raumluft. Lüfter ausschalten."
    neighbour = _room(fan_on=True, aligned="close", delta_g_m3=0.2, reference_path="neighbour_room")
    assert fan_stop_message(neighbour) == "Die Zuluft aus dem Nebenraum ist kaum noch trockener als die Raumluft. Lüfter ausschalten."
    failed = _with(_room(fan_on=True, aligned="close", delta_g_m3="x", reference_path="neighbour_room"), {"command": "off", "command_state": "failed"})
    assert fan_stop_message(failed) == ("Die Zuluft aus dem Nebenraum ist kaum noch trockener als die Raumluft. "
                                        "Automatisches Ausschalten hat nicht geklappt. Lüfter ausschalten.")


def test_events_tell_status_instead_of_a_task_and_stay_compatible() -> None:
    auto = _with(_room(fan_on=True, aligned="close", action="Close"), OWNED)
    payload = room_payload(auto, previous_action="Continue ventilating", language="de", entry_id="e")
    assert (payload["action"], payload["category"]) == ("close", "status")  # the raw action stays
    assert payload["action_label"] == "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung"
    assert payload["fan_automation"]["state"] == "stopping"
    english = recommendation_payload(auto, previous_recommendation="continue_ventilating", language="en", entry_id="e")
    assert (english["recommendation"], english["category"]) == ("close", "status")
    assert english["recommendation_label"] == "Airing goal reached – FreshAirIQ ends the airing"
    manual = _room(fan_on=True, aligned="close", action="Close")
    payload = room_payload(manual, previous_action=None, language="de", entry_id="e")
    assert (payload["category"], payload["action_label"], payload["fan_automation"]) == ("action", "Bitte Lüfter ausschalten", None)
    start = _with(_room(action="Ventilate"), {})
    assert room_payload(start, previous_action=None, language="de", entry_id="e")["category"] == "status"
    assert handled_label(start, "close") is None and handled_label(start, "ventilate", "en").startswith("Automatic airing recommended")


def test_notifications_and_reminders_follow_the_automation() -> None:
    auto = _with(_room(fan_on=True, aligned="close", action="Close", active=True), OWNED)
    assert auto_room_event("close", auto, "Bitte Lüfter ausschalten") == (
        "fan_auto", "FreshAirIQ · Garage", "Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung.")
    manual = _room(fan_on=True, aligned="close", action="Close")
    assert auto_room_event("close", manual, "Lüfter ausschalten")[0] == "close"
    rooms = {"garage": auto}
    assert auto_house({"kind": "close", "room_keys": ["garage"]}, rooms)
    assert not auto_house({"kind": "close", "room_keys": ["garage", "x"]}, rooms)
    start = _with(_room(action="Ventilate"), {})
    assert house_handled_by_automation("ventilate", ["garage"], {"garage": start})
    assert not house_handled_by_automation("wait", ["garage"], {"garage": start})
    assert not house_handled_by_automation("close", [], rooms)

    class Store:
        def __init__(self):
            self.rooms = {"garage": {"last_action": "Close", "action_notified_at": "2026-10-24T10:00:00+00:00"}}

        def room(self, key):
            return self.rooms.setdefault(key, {})

    events, _ = room_notification_events(rooms, Store(), T0, {"action_reminder_min": 5}, {}, sensor_alerts=lambda r: False)
    assert events["reminder"] == []  # nothing to remind of: FreshAirIQ switches the fan off itself
    events, _ = room_notification_events({"garage": manual | {"active": True}}, Store(), T0, {"action_reminder_min": 5}, {}, sensor_alerts=lambda r: False)
    assert [r["key"] for r in events["reminder"]] == ["garage"]


def test_new_texts_have_english_translations() -> None:
    for german, english in (
        ("FreshAirIQ beendet die automatische Lüftung in Garage", "FreshAirIQ ends the automatic airing in Garage"),
        ("Bad schließen · FreshAirIQ beendet die automatische Lüftung in Garage", "Close Bad · FreshAirIQ ends the automatic airing in Garage"),
        ("Automatische Lüftung in Garage läuft · noch ca. 4 min", "Automatic airing in Garage is running · about 4 min left"),
        ("Lüftungsziel erreicht – FreshAirIQ beendet die Lüftung.", "Airing goal reached – FreshAirIQ ends the airing."),
        ("Vergleichsluft ist die Zuluft aus dem Nebenraum (Ablüfter), nicht die Außenluft",
         "The reference air is the air drawn in from the neighbouring room (exhaust fan), not the outdoor air"),
    ):
        assert to_english(german, {"Garage", "Bad"}) == english


# --------------------------------------------------------------------------- neighbouring-room reference
def test_neighbour_reference_is_the_basis_before_the_automatic_start() -> None:
    applies = exhaust_reference_applies
    assert applies(fan_configured=True, fan_active=False, window_open=False, has_contacts=True, auto_start=True)
    assert not applies(fan_configured=True, fan_active=False, window_open=False, has_contacts=True)  # manual fan: window air
    assert applies(fan_configured=True, fan_active=True, window_open=False, has_contacts=True)
    assert not applies(fan_configured=True, fan_active=True, window_open=True, has_contacts=True, auto_start=True)
    assert applies(fan_configured=True, fan_active=False, window_open=False, has_contacts=False)
    assert not applies(fan_configured=False, fan_active=False, window_open=False, has_contacts=False, auto_start=True)
