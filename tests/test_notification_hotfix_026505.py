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
    hass, store = _hass(), _Store()
    options = _push_options(notification_targets=["phone", "tablet"])
    rooms = {"bad": _room()}
    for minute in (0, 2, 4):
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
