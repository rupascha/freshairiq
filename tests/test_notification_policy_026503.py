"""0.26.5.3 (community, HarryP): action vs. status messages, reminders, no contradictions.

* every ``freshairiq_notification`` and bus event carries ``category``
  (action / status / warning);
* "Statusmeldungen ausgeben" (on by default) switches status messages off;
* "Erinnerung an offene Aktion" repeats a still open room action after 5–60 min;
* room messages follow the house-aligned recommendation: no "please air" while
  the house deliberately waits, no "please close" while the house keeps the
  room open in a joint airing.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from tests.test_user_feedback_026409 import T0, _hass, _options, _room, _Store  # installs the HA stubs

from custom_components.freshairiq.automation_events import (
    action_category,
    house_category,
    notification_category,
)
from custom_components.freshairiq.notification_policy import (
    effective_room_action,
    reminder_interval_min,
    status_messages_wanted,
)
from custom_components.freshairiq.notifications import EVENT_NOTIFICATION, process_notifications


def _types(hass) -> list[str]:
    return [d["type"] for e, d in hass.bus.events if e == EVENT_NOTIFICATION]


def test_categories() -> None:
    assert [action_category(c) for c in ("close", "ventilate", "close_fan", "check_sensor", "continue_ventilating", "okay", "ventilate_later")] == [
        "action", "action", "action", "warning", "status", "status", "status"]
    assert [house_category(k) for k in ("ventilate", "close", "sensor", "continue", "wait", "end", None)] == [
        "action", "action", "warning", "status", "status", "status", "status"]
    assert [notification_category(t) for t in ("close", "cool", "mould", "sensor", "complete", "learning", "night", "house_close", "house_continue")] == [
        "action", "action", "warning", "warning", "status", "status", "status", "action", "status"]


def test_options_and_effective_action() -> None:
    assert status_messages_wanted({}, "complete") and not status_messages_wanted({"notify_status_messages": False}, "complete")
    assert status_messages_wanted({"notify_status_messages": False}, "close")
    assert [reminder_interval_min({"action_reminder_min": v}) for v in (0, None, "x", float("nan"), 2, 15, 500)] == [
        None, None, None, None, 5.0, 15.0, 60.0]
    assert effective_room_action(_room(action="Ventilate", house_aligned_action="ventilate_later")) == "ventilate_later"
    assert effective_room_action(_room(action="Close", house_aligned_action="monitor_open")) == "monitor_open"
    assert effective_room_action(_room(action="Close", house_aligned_action="close")) == "Close"
    assert effective_room_action(_room(action="Close")) == "Close"
    joint = {"kind": "continue", "room_keys": ["bad", "flur"]}
    assert effective_room_action(_room(action="Close", house_aligned_action="close"), joint) == "Continue ventilating"
    assert effective_room_action(_room(action="Close", house_aligned_action="close"), {"kind": "continue", "room_keys": ["flur"]}) == "Close"


def test_every_notification_event_carries_its_category() -> None:
    hass, store = _hass(), _Store()
    data = {"rooms": {"bad": _room(action="Close", active=True)}, "intelligent_recommendation": {
        "kind": "close", "status": "close_windows", "room_keys": ["bad"], "title": "Jetzt schließen", "instruction": "Bad schließen"}}
    asyncio.run(process_notifications(hass, store, data, _options(), T0, []))
    assert [(d["type"], d["category"]) for _, d in hass.bus.events] == [("close", "action"), ("house_close", "action")]


def test_status_messages_can_be_switched_off() -> None:
    sessions = [{"key": "bad", "name": "Bad", "learning_valid": True, "removed_ml": 120, "temp_delta_c": -0.8, "cost": 0.03}]
    running = {"rooms": {}, "intelligent_recommendation": {"kind": "continue", "status": "ventilation_running", "room_keys": ["bad"],
               "title": "Weiterlüften", "instruction": "Bad offen lassen"}}
    on, off = _hass(), _hass()
    asyncio.run(process_notifications(on, _Store(), running, _options(), T0, sessions))
    asyncio.run(process_notifications(off, _Store(), running, _options(notify_status_messages=False), T0, sessions))
    assert set(_types(on)) == {"house_continue", "complete", "learning"}
    assert _types(off) == []
    # actions and warnings stay
    hass = _hass()
    data = {"rooms": {"bad": _room(action="Close", active=True, mould_level="High", surface_rh=85)}}
    asyncio.run(process_notifications(hass, _Store(), data, _options(notify_status_messages=False), T0, []))
    assert _types(hass) == ["close"]  # mould waits while the window is open (0.26.4.6)


def test_status_pushes_follow_the_switch_too() -> None:
    sessions = [{"key": "bad", "name": "Bad", "learning_valid": True, "removed_ml": 120, "temp_delta_c": -0.8, "cost": 0.03}]
    push = _options(notifications_enabled=True, notification_targets=["phone"], notify_status_messages=False)
    hass = _hass()
    asyncio.run(process_notifications(hass, _Store(), {"rooms": {}}, push, T0, sessions))
    assert hass.services.calls == []
    hass = _hass()
    asyncio.run(process_notifications(hass, _Store(), {"rooms": {}}, {**push, "notify_status_messages": True}, T0, sessions))
    assert hass.services.calls


def test_an_open_action_is_repeated_after_the_reminder_interval() -> None:
    hass, store = _hass(), _Store()
    options = _options(action_reminder_min=15, notifications_enabled=True, notification_targets=["phone"])
    data = {"rooms": {"bad": _room(action="Close", active=True)}}
    asyncio.run(process_notifications(hass, store, data, options, T0, []))
    assert _types(hass) == ["close"]
    asyncio.run(process_notifications(hass, store, data, options, T0 + timedelta(minutes=10), []))
    assert _types(hass) == ["close"]
    asyncio.run(process_notifications(hass, store, data, options, T0 + timedelta(minutes=15), []))
    assert _types(hass) == ["close", "close"]
    reminder = hass.bus.events[-1][1]
    assert reminder["reminder"] is True and reminder["message"].startswith("Erinnerung: ")
    assert len(hass.services.calls) == 2  # the push is repeated as well, despite the 90-min cooldown
    asyncio.run(process_notifications(hass, store, data, options, T0 + timedelta(minutes=20), []))
    assert _types(hass) == ["close", "close"]
    # done: the window was closed – no further reminder
    closed = {"rooms": {"bad": _room(action="Close", active=False)}}
    asyncio.run(process_notifications(hass, store, closed, options, T0 + timedelta(minutes=45), []))
    assert _types(hass) == ["close", "close"]


def test_reminders_for_airing_and_cooling_and_state_from_older_versions() -> None:
    hass, store = _hass(), _Store()
    options = _options(action_reminder_min=5, notify_cooling=True)
    store.room("bad")["last_action"] = "Ventilate"  # stored by 0.26.5.2, no timestamp yet
    store.room("kueche")["last_action"] = "Ventilate for cooling"
    data = {"rooms": {"bad": _room(), "kueche": _room(key="kueche", name="Küche", action="Ventilate for cooling")}}
    asyncio.run(process_notifications(hass, store, data, options, T0, []))
    assert _types(hass) == []  # counting starts now
    asyncio.run(process_notifications(hass, store, data, options, T0 + timedelta(minutes=5), []))
    assert sorted(_types(hass)) == ["cool", "ventilate"]
    assert all(d["message"].startswith("Erinnerung: ") for _, d in hass.bus.events)


def test_no_reminder_by_default_and_a_room_is_not_told_to_close_during_a_joint_airing() -> None:
    hass, store = _hass(), _Store()
    joint = {"kind": "continue", "status": "ventilation_running", "room_keys": ["bad"], "title": "Weiterlüften",
             "instruction": "Wohnung gemeinsam weiterlüften"}
    data = {"rooms": {"bad": _room(action="Close", house_aligned_action="close", active=True)}, "intelligent_recommendation": joint}
    for minute in (0, 30, 120):
        asyncio.run(process_notifications(hass, store, data, _options(), T0 + timedelta(minutes=minute), []))
    assert _types(hass) == ["house_continue"]


def test_a_damaged_reminder_timestamp_restarts_the_interval() -> None:
    hass, store = _hass(), _Store()
    store.room("bad").update({"last_action": "Close", "action_notified_at": "kaputt"})
    data = {"rooms": {"bad": _room(action="Close", active=True)}}
    asyncio.run(process_notifications(hass, store, data, _options(action_reminder_min=5), T0, []))
    assert _types(hass) == [] and store.room("bad")["action_notified_at"] == T0.isoformat()
    asyncio.run(process_notifications(hass, store, data, _options(action_reminder_min=5), T0 + timedelta(minutes=5), []))
    assert _types(hass) == ["close"]
