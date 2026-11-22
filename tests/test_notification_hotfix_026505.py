"""0.26.5.5 notification hotfix: title with the action, readable text, honest reasons, push retry.

F1  The title names the effective action ("FreshAirIQ · Bad · Jetzt lüften"); a reminder is marked;
    a status (FreshAirIQ switches the fan itself) names no task; a fan-only close never asks to close
    a window; the house push of an automatic airing is a status, not "Jetzt schließen".
F2  Plain text in a fixed order: recommendation, "Warum:" with at most three reasons, details. A room
    never borrows the reasons of a contradicting raw action. Events keep their fields; speech is one line.
F3  The dryness reason names the threshold the decision used (active source, hysteresis, profile), and
    the moisture source shows a model indicator, not a percentage of "Sicherheit".
F4  A room push that was attempted and not accepted is retried (bounded); held-back pushes (options,
    night, room selection, presence, cooldown) are not; "close was said" is stored once it is out.
"""
from __future__ import annotations

import asyncio
import copy
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from tests.test_user_feedback_026409 import T0, _Bus, _options, _room, _Store  # installs the HA stubs

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.fan_automation import room_fan_automation
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room
from custom_components.freshairiq.notification_policy import PUSH_PENDING, record_room_push
from custom_components.freshairiq.notification_text import message_body, room_title, speech_text
from custom_components.freshairiq.notifications import EVENT_NOTIFICATION, _house_message, process_notifications
from custom_components.freshairiq.room_recommendation import _recommendation

EVENT_FIELDS = {"type", "category", "room_key", "room_name", "title", "message", "speech", "night_quiet_hours", "created_at"}
REASONS = ["Raumluftfeuchte 70 % ist zu hoch (Grenze 68 %)", "Außen-/Referenzluft ist 3.1 g/m³ trockener (mindestens 1.5 g/m³ nötig)",
           "Aktuell sind etwa 120 ml Feuchtigkeit entfernbar", "Windrichtung unterstützt den Luftwechsel"]


class _Services:
    """notify.<name> services that can disappear and come back."""

    def __init__(self, available=("phone",)):
        self.available = set(available)
        self.calls: list[tuple[str, str, dict]] = []

    def has_service(self, domain, service):
        return domain == "notify" and service in self.available

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data))


def _hass(language="de", available=("phone",), states=None):
    return SimpleNamespace(services=_Services(available), bus=_Bus(), config=SimpleNamespace(language=language),
                           states=SimpleNamespace(get=lambda entity_id: (states or {}).get(entity_id)))


def _push_options(**extra):
    return _options(**{"notifications_enabled": True, "notification_targets": ["phone"], "notify_cooling": True, **extra})


def _events(hass):
    return [d for e, d in hass.bus.events if e == EVENT_NOTIFICATION]


def _run(hass, store, rooms, now, options=None, iq=None):
    data = {"rooms": rooms, **({"intelligent_recommendation": iq} if iq else {})}
    return asyncio.run(process_notifications(hass, store, data, options or _push_options(), now, []))


def _push(hass, index=-1):
    return hass.services.calls[index][2]


# --- F1 / F2: title and text ----------------------------------------------------------------

def test_f1_f2_ventilate_title_names_the_action_and_the_text_is_ordered() -> None:
    hass, store = _hass(), _Store()
    _run(hass, store, {"bad": _room(recommendation_reasons=REASONS)}, T0)
    push = _push(hass)
    assert push["title"] == "FreshAirIQ · Bad · Jetzt lüften"
    lines = push["message"].split("\n")
    assert lines[0].endswith(". Alternativ den Lüfter einschalten.") and lines[1] == "Warum:"
    assert lines[2:] == [f"• {r}" for r in REASONS[:3]]  # at most three reasons, in their order
    event = _events(hass)[0]
    assert set(event) == EVENT_FIELDS and event["type"] == "ventilate" and event["category"] == "action"
    assert event["title"] == push["title"] and event["message"] == push["message"]
    assert "\n" not in event["speech"] and "•" not in event["speech"]
    assert event["speech"].startswith("Bad: ") and "Warum: Raumluftfeuchte 70 % ist zu hoch (Grenze 68 %)." in event["speech"]


def test_f1_f2_english_title_and_text_keep_the_room_name() -> None:
    hass, store = _hass("en"), _Store()
    _run(hass, store, {"bad": _room(recommendation_reasons=REASONS)}, T0)
    push = _push(hass)
    assert push["title"] == "FreshAirIQ · Bad · Ventilate now"
    lines = push["message"].split("\n")
    assert lines[1] == "Why:" and lines[2] == "• Room humidity 70 % is too high (limit 68 %)"
    assert lines[3] == "• Outdoor/reference air is 3.1 g/m³ drier (at least 1.5 g/m³ needed)"
    assert _events(hass)[0]["speech"].startswith("Bad: ") and "Why: Room humidity 70 %" in _events(hass)[0]["speech"]


@pytest.mark.parametrize(("language", "title", "detail"), [
    ("de", "FreshAirIQ · Bad · Jetzt schließen", "Weitere 5 Min: "),
    ("en", "FreshAirIQ · Bad · Close now", "Next 5 min: "),
])
def test_f1_f2_close_title_and_details_last(language, title, detail) -> None:
    hass, store = _hass(language), _Store()
    room = _room(action="Close", active=True, recommendation_reasons=["Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering"],
                 configured_actuators={"window_open": True})
    _run(hass, store, {"bad": room}, T0)
    push = _push(hass)
    lines = push["message"].split("\n")
    assert push["title"] == title and lines[1] in {"Warum:", "Why:"} and lines[-1].startswith(detail) and len(lines) == 4


@pytest.mark.parametrize(("language", "title"), [("de", "FreshAirIQ · Bad · Kühlen"), ("en", "FreshAirIQ · Bad · Cool down")])
def test_f1_cooling_title(language, title) -> None:
    hass, store = _hass(language), _Store()
    _run(hass, store, {"bad": _room(action="Ventilate for cooling", configured_actuators={})}, T0)
    assert _push(hass)["title"] == title and _events(hass)[0]["type"] == "cool"


@pytest.mark.parametrize(("language", "title", "prefix"), [
    ("de", "FreshAirIQ · Bad · Erinnerung: Jetzt schließen", "Erinnerung: "),
    ("en", "FreshAirIQ · Bad · Reminder: Close now", "Reminder: "),
])
def test_f1_a_reminder_is_marked_in_the_title(language, title, prefix) -> None:
    hass, store = _hass(language), _Store()
    options = _push_options(action_reminder_min=15)
    room = _room(action="Close", active=True, configured_actuators={"window_open": True})
    _run(hass, store, {"bad": room}, T0, options)
    _run(hass, store, {"bad": room}, T0 + timedelta(minutes=15), options)
    reminder = _push(hass)
    assert reminder["title"] == title and reminder["message"].startswith(prefix) and _events(hass)[-1]["reminder"] is True


def _auto_fan_room():
    room = {"key": "bad", "name": "Bad", "action": "Close", "active": True, "data_quality": "ok", "mould_level": "Low", "surface_rh": 60,
            "house_aligned_action": "close", "delta_g_m3": 0.2, "recommendation_reasons": ["Lüftungsziel erreicht oder zusätzlicher Nutzen ist zu gering"],
            "configured_actuators": {"exhaust_fan_control": "recommendation", "exhaust_fan": ["switch.a"], "mechanical_exhaust_active": True}}
    room["fan_automation"] = room_fan_automation(room, {"owned": True, "command": "on", "command_state": "confirmed"})
    return room


def test_f1_an_automatic_fan_is_a_status_without_a_task_in_the_title() -> None:
    hass, store = _hass(), _Store()
    _run(hass, store, {"bad": _auto_fan_room()}, T0)
    event = _events(hass)[0]
    assert event["type"] == "fan_auto" and event["category"] == "status"
    assert event["title"] == "FreshAirIQ · Bad" and _push(hass)["title"] == "FreshAirIQ · Bad"
    assert event["message"] == "Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus."


@pytest.mark.parametrize(("language", "title"), [("de", "FreshAirIQ · Bad · Lüfter ausschalten"), ("en", "FreshAirIQ · Bad · Switch off the fan")])
def test_f1_a_fan_only_close_never_asks_to_close_a_window(language, title) -> None:
    hass, store = _hass(language), _Store()
    room = _room(action="Close", active=True, configured_actuators={"exhaust_fan": "fan.bad", "mechanical_exhaust_active": True})
    _run(hass, store, {"bad": room}, T0)
    push = _push(hass)
    assert push["title"] == title
    assert "Fenster" not in push["title"] + push["message"] and "window" not in push["title"] + push["message"]


@pytest.mark.parametrize(("key", "title"), [("failed_off", "Lüfter ausschalten"), ("failed_on", "Lüfter einschalten"), ("partial", "Lüfter prüfen")])
def test_f1_a_fan_task_names_the_fan(key, title) -> None:
    room = {"name": "Bad", "fan_automation": {"user_action_needed": True, "label_key": key}}
    event = "close" if key == "failed_off" else "ventilate"
    from custom_components.freshairiq import notification_text
    original = notification_text.handled_label
    notification_text.handled_label = lambda _room, _code: "x"
    try:
        assert room_title(event, room) == f"FreshAirIQ · Bad · {title}"
    finally:
        notification_text.handled_label = original


def test_f2_a_house_aligned_action_never_borrows_contradicting_room_reasons() -> None:
    hass, store = _hass(), _Store()
    wait = _room(action="Wait", house_aligned_action="ventilate", configured_actuators={},
                 recommendation_reasons=["Lüften noch nicht wirksam genug: Außen-/Referenzluft ist nur 1.0 g/m³ trockener; benötigt werden etwa 2.5 g/m³"])
    _run(hass, store, {"bad": wait}, T0)
    push = _push(hass)
    assert push["title"] == "FreshAirIQ · Bad · Jetzt lüften"
    assert "Warum" not in push["message"] and "nicht wirksam" not in push["message"] and "\n" not in push["message"]


def test_f1_f2_house_text_is_ordered_and_an_automatic_house_airing_is_a_status() -> None:
    iq = {"kind": "ventilate", "title": "Jetzt lüften", "instruction": "Bad öffnen", "summary": "Etwa 300 ml entfernbar",
          "reasons": ["Grund 1", "Grund 2", "Grund 3", "Grund 4"], "secondary": "Danach schließen", "room_keys": ["bad"]}
    title, text = _house_message(iq, {"bad": _room()})
    assert title == "FreshAirIQ · Jetzt lüften"
    assert text.split("\n") == ["Bad öffnen Alternativ den Lüfter einschalten (Bad).", "Etwa 300 ml entfernbar", "Warum:",
                                "• Grund 1", "• Grund 2", "• Grund 3", "Danach schließen"]
    auto = {"kind": "close", "title": "Jetzt schließen", "instruction": "Bad schließen", "room_keys": ["bad"]}
    title, text = _house_message(auto, {"bad": _auto_fan_room()})
    assert title == "FreshAirIQ · Automatische Lüftung"
    assert text == "Bad: Lüftungsziel erreicht – FreshAirIQ prüft kurz und schaltet die Lüftung dann aus."


def test_f2_helpers() -> None:
    assert message_body("Jetzt lüften.", ["", None, "a"], ["", "Detail"]) == "Jetzt lüften.\nWarum:\n• a\nDetail"
    assert message_body("Jetzt lüften.") == "Jetzt lüften."
    assert speech_text("Jetzt lüften.\nWarum:\n• a\n• b!\n\nDetail") == "Jetzt lüften. Warum: a. b! Detail."
    assert room_title("mould", {"key": "bad"}) == "FreshAirIQ · bad"


# --- F3: the reason names the threshold the decision used --------------------------------------

def _ref_rh(delta, temp, rh, ref_t):
    """Reference humidity at ``ref_t`` that is ``delta`` g/m³ drier than the room."""
    target, low, high = absolute_humidity(temp, rh) - delta, 1.0, 100.0
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if absolute_humidity(ref_t, mid) < target else (low, mid)
    return (low + high) / 2


def _reasons(rh, delta, *, source=False, latched=False, profile="comfort"):
    options = {**DEFAULT_OPTIONS, "operating_profile": profile}
    room = RoomInput("bad", "Bad", 22.0, rh, 15.0, _ref_rh(delta, 22.0, rh, 15.0), 30.0, False, 0, moisture_source_active=source,
                     moisture_source_label="Dusche", moisture_source_confidence=72, moisture_source_rate_ml_min=5.0, ventilation_latched=latched)
    result = evaluate_room(room, options, False)
    action, _text, reasons = _recommendation(result, options, pollen=0.0, co2=None, airflow=1.0, wind_bearing=None, wind_speed=None,
                                             ventilation_latched=latched)
    return action, reasons


def test_f3_an_active_source_needs_only_the_close_threshold() -> None:
    action, reasons = _reasons(63.0, 2.3, source=True)
    assert action == "Ventilate"
    assert "Außen-/Referenzluft ist 2.3 g/m³ trockener; bei aktiver Feuchtequelle genügen 0.4 g/m³" in reasons
    assert not any("mindestens 2.5" in r for r in reasons)
    assert "Dusche wahrscheinlich aktiv (Modellindikator 72/100); interne Feuchteproduktion etwa 300 ml/h" in reasons
    assert not any("Sicherheit" in r or "72 %" in r for r in reasons)


def test_f3_without_a_source_2_3_is_not_enough_and_2_6_meets_the_normal_threshold() -> None:
    assert _reasons(63.0, 2.3)[0] == "Wait"
    action, reasons = _reasons(63.0, 2.6)
    assert action == "Ventilate" and "Außen-/Referenzluft ist 2.6 g/m³ trockener (mindestens 2.5 g/m³ nötig)" in reasons


@pytest.mark.parametrize(("rh", "delta", "kwargs", "needed"), [
    (70.0, 1.6, {}, "1.5"),                                  # high humidity
    (70.0, 3.0, {}, "1.5"),                                  # both met: the smaller one is needed
    (61.0, 2.2, {"latched": True}, "2.1"),                   # hysteresis: 62 − 2 %, 2.5 − 0.4 g/m³
    (61.0, 2.2, {"profile": "dehumidify"}, "2.1"),           # dehumidify: 62 − 2 %, 2.5 × 0.85 g/m³
    (60.0, 1.8, {"profile": "dehumidify", "latched": True}, "1.7"),
])
def test_f3_hysteresis_profile_and_high_humidity(rh, delta, kwargs, needed) -> None:
    action, reasons = _reasons(rh, delta, **kwargs)
    assert action == "Ventilate"
    assert f"Außen-/Referenzluft ist {delta:.1f} g/m³ trockener (mindestens {needed} g/m³ nötig)" in reasons


def test_f3_critical_co2_states_no_dryness_threshold() -> None:
    options = dict(DEFAULT_OPTIONS)
    room = RoomInput("bad", "Bad", 22.0, 50.0, 15.0, _ref_rh(0.5, 22.0, 50.0, 15.0), 30.0, False, 0, co2=1600.0)
    result = evaluate_room(room, options, False)
    action, _text, reasons = _recommendation(result, options, pollen=0.0, co2=1600.0, airflow=1.0, wind_bearing=None, wind_speed=None)
    assert action == "Ventilate" and not any("trockener" in r for r in reasons)


# --- F4: room push retry -------------------------------------------------------------------

def test_f4_a_missing_service_gets_the_push_once_it_is_back() -> None:
    hass, store = _hass(available=()), _Store()
    rooms = {"bad": _room()}
    _run(hass, store, rooms, T0)
    assert hass.services.calls == [] and store.room("bad")[PUSH_PENDING]["action"] == "Ventilate"
    _run(hass, store, rooms, T0 + timedelta(seconds=30))  # still missing, and not yet a minute
    hass.services.available.add("phone")
    _run(hass, store, rooms, T0 + timedelta(seconds=45))
    assert hass.services.calls == []  # at most once a minute
    _run(hass, store, rooms, T0 + timedelta(minutes=1, seconds=30))
    assert len(hass.services.calls) == 1 and _push(hass)["title"] == "FreshAirIQ · Bad · Jetzt lüften"
    assert PUSH_PENDING not in store.room("bad")
    for minute in (3, 5, 30):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute))
    assert len(hass.services.calls) == 1 and [e["type"] for e in _events(hass)] == ["ventilate"]  # the event once


def test_f4_after_a_restart_the_push_follows_once() -> None:
    hass, store = _hass(available=()), _Store()
    rooms = {"bad": _room()}
    _run(hass, store, rooms, T0)
    restarted = _Store()
    restarted.data, restarted.rooms = copy.deepcopy(store.data), copy.deepcopy(store.rooms)
    hass2 = _hass()
    for minute in (2, 3, 4):
        _run(hass2, restarted, rooms, T0 + timedelta(minutes=minute))
    assert len(hass2.services.calls) == 1 and _events(hass2) == []


def test_f4_the_retry_ends_after_its_window() -> None:
    hass, store = _hass(available=()), _Store()
    rooms = {"bad": _room()}
    _run(hass, store, rooms, T0)
    hass.services.available.add("phone")
    _run(hass, store, rooms, T0 + timedelta(minutes=31))
    assert hass.services.calls == [] and PUSH_PENDING not in store.room("bad")


def test_f4_no_late_push_once_the_action_changed_or_was_done() -> None:
    hass, store = _hass(available=()), _Store()
    _run(hass, store, {"bad": _room()}, T0)
    hass.services.available.add("phone")
    _run(hass, store, {"bad": _room(active=True, action="Continue ventilating")}, T0 + timedelta(minutes=2))
    _run(hass, store, {"bad": _room(active=True, action="Continue ventilating")}, T0 + timedelta(minutes=4))
    assert hass.services.calls == []
    # opened: the ventilate push of the same action is no longer valid either
    hass, store = _hass(available=()), _Store()
    _run(hass, store, {"bad": _room()}, T0)
    hass.services.available.add("phone")
    _run(hass, store, {"bad": _room(active=True)}, T0 + timedelta(minutes=2))
    assert hass.services.calls == [] and PUSH_PENDING not in store.room("bad")


def test_f4_a_close_push_is_retried_and_close_is_stored_only_once_it_is_out() -> None:
    hass, store = _hass(available=()), _Store()
    room = _room(action="Close", active=True, configured_actuators={"window_open": True})
    _run(hass, store, {"bad": room}, T0)
    assert "last_close_message_at" not in store.room("bad")
    hass.services.available.add("phone")
    _run(hass, store, {"bad": room}, T0 + timedelta(minutes=2))
    assert len(hass.services.calls) == 1 and store.room("bad")["last_close_message_at"] == (T0 + timedelta(minutes=2)).isoformat()
    # GitHub #15 still holds: no "ventilate" right after the close message
    _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=5))
    assert len(hass.services.calls) == 1


def test_f4_with_pushes_off_close_is_stored_with_the_event() -> None:
    hass, store = _hass(), _Store()
    room = _room(action="Close", active=True, configured_actuators={"window_open": True})
    _run(hass, store, {"bad": room}, T0, _options())
    assert store.room("bad")["last_close_message_at"] == T0.isoformat() and PUSH_PENDING not in store.room("bad")


def test_f4_two_targets_one_accepted_means_no_duplicate() -> None:
    # 0.26.7.2: the configured "tablet" without a service is waited for within the retry window (not given up at once)
    hass, store = _hass(), _Store()
    options = _push_options(notification_targets=["phone", "tablet"])
    rooms = {"bad": _room()}
    for minute in (0, 2, 4):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options)
    assert len(hass.services.calls) == 1 and PUSH_PENDING in store.room("bad")
    for minute in (31, 33, 35):                                                       # the window is over: done, nothing more
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options)
    assert len(hass.services.calls) == 1 and PUSH_PENDING not in store.room("bad")


@pytest.mark.parametrize("options", [
    _push_options(notify_ventilate=False),                                           # disabled
    _push_options(notification_room_keys=["kueche"]),                                 # room not selected
    _push_options(notification_scope="house"),                                        # scope
    _push_options(suppress_notifications_at_night=True, night_start_hour="09:00", night_end_hour="11:00"),  # night
    _push_options(notify_only_when_home=True, adult_presence_entities=["person.a"]),  # presence: away
])
def test_f4_a_held_back_push_is_not_retried(options) -> None:
    hass, store = _hass(states={"person.a": SimpleNamespace(state="not_home", entity_id="person.a")}), _Store()
    rooms = {"bad": _room()}
    _run(hass, store, rooms, T0, options)
    assert PUSH_PENDING not in store.room("bad")
    later = {**options, "notify_ventilate": True, "notification_room_keys": [], "notification_scope": "both",
             "suppress_notifications_at_night": False, "notify_only_when_home": False}
    for minute in (2, 4):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), later)
    assert hass.services.calls == [] and len(_events(hass)) == 1


def test_f4_a_push_inside_the_cooldown_is_not_sent_again() -> None:
    hass, store = _hass(), _Store()
    store.data["notifications"] = {"ventilate:bad": (T0 - timedelta(minutes=10)).isoformat()}
    for minute in (0, 2, 4):
        _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=minute))
    assert hass.services.calls == [] and PUSH_PENDING not in store.room("bad")


def test_f4_an_exception_of_the_notify_service_is_retried() -> None:
    hass, store = _hass(), _Store()

    async def broken(domain, service, data, blocking=False):
        raise RuntimeError("service down")

    working = hass.services.async_call
    hass.services.async_call = broken
    _run(hass, store, {"bad": _room()}, T0)
    assert store.room("bad")[PUSH_PENDING]["first_at"] == T0.isoformat()
    _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=1))  # fails again: the window still counts from the first try
    assert store.room("bad")[PUSH_PENDING]["first_at"] == T0.isoformat()
    hass.services.async_call = working
    _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=2))
    assert len(hass.services.calls) == 1


def test_f4_record_and_damaged_state() -> None:
    mem = {"last_action": "Ventilate"}
    assert record_room_push(mem, {"action": None}, False, T0) is False
    assert record_room_push(mem, {"action": "Close"}, False, T0) is False  # not the room's action any more
    hass, store = _hass(), _Store()
    store.room("bad").update(last_action="Ventilate", action_notified_at=T0.isoformat(), **{PUSH_PENDING: "broken"})
    _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=1))
    assert PUSH_PENDING not in store.room("bad") and hass.services.calls == []


# --- 0.26.7.2 (#30): the room push names the cause the room model decided on ----------------------------------------

from custom_components.freshairiq.room_recommendation import benefit_close_text  # noqa: E402

_BENEFIT_REASON = benefit_close_text(8.0, 24.15, 65.0, {"target_rh": 58.0})


@pytest.mark.parametrize(("kind", "language", "lead"), [
    ("benefit_exhausted", "de", "Weiteres Lüften entfernt kaum noch Feuchtigkeit – das Feuchteziel ist noch nicht erreicht. Jetzt schließen."),
    ("benefit_exhausted", "en", "Further airing hardly removes moisture any more – the humidity target is not reached yet. Close now."),
    ("goals_reached", "de", "Feuchteziel erreicht – die Ziele des Raums sind erfüllt. Jetzt schließen."),
    ("goals_reached", "en", "Humidity target reached – the room's goals are met. Close now."),
    ("temperature_limit", "en", "Your temperature limit for airing is reached – close because of the temperature, not because enough moisture was removed. Close now."),
    ("air_no_longer_helps", "de", "Die Außenluft trocknet den Raum nicht mehr. Jetzt schließen."),
])
def test_the_room_close_push_names_the_actual_cause(kind, language, lead) -> None:
    hass, store = _hass(language), _Store()
    room = _room(action="Close", active=True, close_recommended=True, close_kind=kind, configured_actuators={"window_open": True},
                 recommendation_reasons=[_BENEFIT_REASON] if kind == "benefit_exhausted" else [])
    _run(hass, store, {"bad": room}, T0)
    push = _push(hass)
    assert push["message"].split("\n")[0] == lead
    if kind == "benefit_exhausted":
        assert "Feuchteziel erreicht" not in push["message"] and "target reached" not in push["message"].lower()
        assert ("Feuchteziel von 58 % noch nicht erreicht" if language == "de" else "humidity target of 58 % is not reached yet") in push["message"]
    event = _events(hass)[0]
    assert event["message"] == push["message"] and event["speech"].startswith(f"Bad: {lead}")
    # the same close is pushed once: further cycles, also with a new variant signature, send nothing more
    for minutes in (1, 2, 30):
        _run(hass, store, {"bad": {**room, "learning_samples": 90}}, T0 + timedelta(minutes=minutes))
    assert len(hass.services.calls) == 1


# --- 0.26.7.2 (support diagnosis 21.11.): one phone for two residents, one of them away ------------------------------------
def _shared_phone_options(order, ben_target="notify.phone"):
    profiles = {"adult:0": {"name": "Anna", "room_keys": ["bad"], "notification_targets": ["notify.phone"]},
                "adult:1": {"name": "Ben", "room_keys": ["bad"], "notification_targets": [ben_target]}}
    return _push_options(notification_targets=[], notify_only_when_home=True, adult_presence_entities=["person.anna", "person.ben"],
                         adult_resident_names="Anna, Ben", resident_room_profiles={slot: profiles[slot] for slot in order})


def _presence(ben="home"):
    return {"person.anna": SimpleNamespace(state="not_home", entity_id="person.anna"),
            "person.ben": SimpleNamespace(state=ben, entity_id="person.ben")}


HOUSE_IQ = {"kind": "ventilate", "title": "Jetzt lüften", "instruction": "Bad öffnen", "room_keys": ["bad"]}


@pytest.mark.parametrize("ben_target", ["notify.phone", "phone"])
@pytest.mark.parametrize("order", [("adult:0", "adult:1"), ("adult:1", "adult:0")], ids=["away_first", "home_first"])
@pytest.mark.parametrize("scope", ["room", "house"])
def test_shared_phone_the_present_resident_gets_the_push_once_also_after_a_retry(order, scope, ben_target) -> None:
    hass, store = _hass(available=(), states=_presence()), _Store()
    options = _shared_phone_options(order, ben_target)
    options["notification_scope"] = scope
    iq = HOUSE_IQ if scope == "house" else None
    _run(hass, store, {"bad": _room()}, T0, options, iq)
    assert hass.services.calls == []                                                   # the service is missing
    hass.services.available.add("phone")
    for minute in (2, 4, 6):
        _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=minute), options, iq)
    assert [(c[1], c[2]["message"][:5]) for c in hass.services.calls] == [("phone", "Ben, ")]


@pytest.mark.parametrize("order", [("adult:0", "adult:1"), ("adult:1", "adult:0")], ids=["anna_first", "ben_first"])
@pytest.mark.parametrize("scope", ["room", "house"])
def test_shared_phone_nobody_at_home_gets_nothing(order, scope) -> None:
    hass, store = _hass(states=_presence(ben="not_home")), _Store()
    options = _shared_phone_options(order)
    options["notification_scope"] = scope
    for minute in (0, 2, 4):
        _run(hass, store, {"bad": _room()}, T0 + timedelta(minutes=minute), options, HOUSE_IQ if scope == "house" else None)
    assert hass.services.calls == [] and PUSH_PENDING not in store.room("bad")


# --- 0.26.7.2 (owner order 21.11.): one recipient key in the delivery ledger, recipients that appear later -------------
def _close_room():
    return _room(action="Close", house_aligned_action="close", active=True)


CLOSE_IQ = {"kind": "close", "title": "Fenster schließen", "instruction": "Bad schließen", "room_keys": ["bad"]}


class _Flaky(_Services):
    """``a`` accepts, ``b`` raises (until healed)."""
    def __init__(self, available, broken=("b",)):
        super().__init__(available)
        self.broken = set(broken)

    async def async_call(self, domain, service, data=None, blocking=False):
        self.calls.append((domain, service, data))
        if service in self.broken:
            raise RuntimeError("Service unavailable")


def _scoped(scope, targets):
    return _push_options(notification_targets=targets, notification_scope=scope, notify_close=True)


@pytest.mark.parametrize("scope", ["room", "house"])
def test_retry_reaches_the_failed_recipient_and_never_the_accepted_one_under_its_alias(scope) -> None:
    hass, store = _hass(available=("a", "b")), _Store()
    hass.services = _Flaky({"a", "b"})
    iq = CLOSE_IQ if scope == "house" else None
    rooms = {"bad": _close_room()}
    _run(hass, store, rooms, T0, _scoped(scope, ["notify.a", "notify.b"]), iq)
    hass.services.broken.clear()
    for minute in (2, 4, 6):                                                           # "a" now listed as "a" (alias)
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), _scoped(scope, ["a", "notify.b"]), iq)
    assert [c[1] for c in hass.services.calls] == ["a", "b", "b"]
    assert store.data.get("notification_deliveries") == {}


@pytest.mark.parametrize("scope", ["room", "house"])
def test_a_ledger_in_the_old_spelling_is_read_by_recipient(scope) -> None:
    hass, store = _hass(), _Store()
    hass.services = _Flaky({"a", "b"})
    iq = CLOSE_IQ if scope == "house" else None
    rooms = {"bad": _close_room()}
    _run(hass, store, rooms, T0, _scoped(scope, ["a", "b"]), iq)
    (key, entry), = store.data["notification_deliveries"].items()
    assert entry["accepted"] == ["notify.a"] and entry["failed"] == {"notify.b": 1}
    # as written before 0.26.7.2: the spelling of the options, no start time
    store.data["notification_deliveries"][key] = {"signature": entry["signature"], "accepted": ["a"], "failed": {"b": 2}}
    _run(hass, store, rooms, T0 + timedelta(minutes=2), _scoped(scope, ["notify.a", "notify.b"]), iq)
    assert [c[1] for c in hass.services.calls] == ["a", "b", "b"]                      # "a" not again, "b" its third try
    assert store.data["notification_deliveries"] == {}                                 # the attempt limit is unchanged


@pytest.mark.parametrize("scope", ["room", "house"])
def test_a_recipient_whose_service_appears_later_gets_the_message_once(scope) -> None:
    hass, store = _hass(available=("a",)), _Store()
    iq = CLOSE_IQ if scope == "house" else None
    rooms, options = {"bad": _close_room()}, _scoped(scope, ["notify.a", "notify.b"])
    _run(hass, store, rooms, T0, options, iq)
    assert [c[1] for c in hass.services.calls] == ["a"]
    (entry,) = store.data["notification_deliveries"].values()
    assert entry["unavailable"] == {"notify.b": T0.isoformat()}                        # noted, the message stays open
    _run(hass, store, rooms, T0 + timedelta(minutes=2), options, iq)
    hass.services.available.add("b")
    for minute in (10, 12, 14):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options, iq)
    assert [c[1] for c in hass.services.calls] == ["a", "b"] and store.data["notification_deliveries"] == {}


@pytest.mark.parametrize("scope", ["room", "house"])
def test_a_notify_entity_that_appears_later_gets_it_once(scope) -> None:
    states = {}
    hass, store = _hass(available=("a", "send_message"), states=states), _Store()
    iq = CLOSE_IQ if scope == "house" else None
    rooms, options = {"bad": _close_room()}, _scoped(scope, ["notify.a", "entity:notify.tablet"])
    _run(hass, store, rooms, T0, options, iq)
    states["notify.tablet"] = SimpleNamespace(state="unknown", entity_id="notify.tablet")
    for minute in (3, 5):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options, iq)
    assert [c[1] for c in hass.services.calls] == ["a", "send_message"]
    assert hass.services.calls[1][2]["entity_id"] == "notify.tablet"


@pytest.mark.parametrize("scope", ["room", "house"])
def test_the_late_recipient_gets_nothing_after_the_window_or_for_a_done_recommendation(scope) -> None:
    iq = CLOSE_IQ if scope == "house" else None
    options = _scoped(scope, ["notify.a", "notify.b"])
    hass, store = _hass(available=("a",)), _Store()
    rooms = {"bad": _close_room()}
    for minute in (0, 10, 20, 31):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options, iq)
    hass.services.available.add("b")
    for minute in (33, 35):                                                           # after the retry window
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options, iq)
    assert [c[1] for c in hass.services.calls] == ["a"]
    # done: the window closed while the service was missing; then the recommendation is over
    hass, store = _hass(available=("a",)), _Store()
    _run(hass, store, rooms, T0, options, iq)
    done_rooms = {"bad": _room(action="Wait", house_aligned_action="wait", active=False)}
    done_iq = {"kind": "wait", "title": "Warten", "instruction": "", "room_keys": []} if iq else None
    _run(hass, store, done_rooms, T0 + timedelta(minutes=2), options, done_iq)
    hass.services.available.add("b")
    for minute in (4, 6, 8):
        _run(hass, store, done_rooms, T0 + timedelta(minutes=minute), options, done_iq)
    assert [c[1] for c in hass.services.calls] == ["a"]


@pytest.mark.parametrize("scope", ["room", "house"])
def test_filters_presence_and_quiet_hours_stay_for_the_late_recipient(scope) -> None:
    iq = CLOSE_IQ if scope == "house" else None
    rooms = {"bad": _close_room()}
    states = {"person.anna": SimpleNamespace(state="home", entity_id="person.anna"),
              "person.ben": SimpleNamespace(state="home", entity_id="person.ben")}
    profiles = {"adult:0": {"name": "Anna", "room_keys": ["bad"], "notification_targets": ["notify.a"]},
                "adult:1": {"name": "Ben", "room_keys": ["bad"], "notification_targets": ["notify.b"]}}
    options = _push_options(notification_targets=[], notification_scope=scope, notify_close=True, notify_only_when_home=True,
                            adult_presence_entities=["person.anna", "person.ben"], adult_resident_names="Anna, Ben",
                            resident_room_profiles=profiles)
    hass, store = _hass(available=("a",), states=states), _Store()
    _run(hass, store, rooms, T0, options, iq)
    states["person.ben"] = SimpleNamespace(state="not_home", entity_id="person.ben")   # Ben leaves: no longer waited for
    hass.services.available.add("b")
    for minute in (2, 4):
        _run(hass, store, rooms, T0 + timedelta(minutes=minute), options, iq)
    assert [c[1] for c in hass.services.calls] == ["a"] and store.data["notification_deliveries"] == {}
    quiet = {**_scoped(scope, ["notify.a", "notify.b"]), "suppress_notifications_at_night": True,
             "night_start_hour": "09:30", "night_end_hour": "11:00"}
    hass, store = _hass(available=("a",)), _Store()
    _run(hass, store, rooms, T0, _scoped(scope, ["notify.a", "notify.b"]), iq)
    hass.services.available.add("b")
    _run(hass, store, rooms, T0 + timedelta(minutes=2), quiet, iq)                     # quiet hours: held back
    assert [c[1] for c in hass.services.calls] == ["a"]


# --- 0.26.7.2 (owner order 21.11., third): the retry window counts from the first attempt, before every retry ----------
def _restarted(store):
    fresh = _Store()
    fresh.data, fresh.rooms = json.loads(json.dumps(store.data)), json.loads(json.dumps(store.rooms))
    return fresh


@pytest.mark.parametrize("restart", [False, True], ids=["running", "after_restart"])
@pytest.mark.parametrize("rounds", [False, True], ids=["no_rounds_between", "rounds_between"])
@pytest.mark.parametrize("minute,b_gets", [(29, 1), (31, 0)])
@pytest.mark.parametrize("scope", ["room", "house"])
def test_the_late_recipient_once_within_the_window_never_after_it_and_a_never_again(scope, minute, b_gets, rounds, restart) -> None:
    iq = CLOSE_IQ if scope == "house" else None
    rooms = {"bad": _close_room()}
    hass, store = _hass(available=("a",)), _Store()
    _run(hass, store, rooms, T0, _scoped(scope, ["notify.a", "notify.b"]), iq)
    for between in (range(2, minute - 1, 3) if rounds else ()):                       # B still missing; "a" also as "a"
        _run(hass, store, rooms, T0 + timedelta(minutes=between), _scoped(scope, ["a" if between % 2 else "notify.a", "notify.b"]), iq)
    if restart:
        store, calls = _restarted(store), hass.services.calls
        hass = _hass(available=("a",)); hass.services.calls = calls
    hass.services.available.add("b")
    for late in (minute, minute + 1, minute + 3):
        _run(hass, store, rooms, T0 + timedelta(minutes=late), _scoped(scope, ["a", "notify.b"]), iq)
    sent = [c[1] for c in hass.services.calls]
    assert (sent.count("a"), sent.count("b")) == (1, b_gets)


@pytest.mark.parametrize("scope", ["room", "house"])
def test_a_new_recommendation_with_the_same_text_is_delivered_again(scope) -> None:
    iq = CLOSE_IQ if scope == "house" else None
    hass, store = _hass(available=("a",)), _Store()
    options = _scoped(scope, ["notify.a", "notify.b"])
    _run(hass, store, {"bad": _close_room()}, T0, options, iq)                          # "b" missing: not done
    wait_iq = {"kind": "wait", "title": "Warten", "instruction": "", "room_keys": []} if iq else None
    _run(hass, store, {"bad": _room(action="Wait", house_aligned_action="wait", active=False)}, T0 + timedelta(minutes=5), options, wait_iq)
    later = T0 + timedelta(minutes=200)                                                 # after the cooldown: the same close again
    _run(hass, store, {"bad": _close_room()}, later, options, iq)
    assert [c[1] for c in hass.services.calls] == ["a", "a"]
