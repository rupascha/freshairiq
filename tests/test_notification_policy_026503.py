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


# 0.26.7.2 (owner order 21.11.): the delivery ledger by recipient, recipients that are not there yet, the retry window
def test_the_delivery_ledger_by_recipient_and_its_retry_window() -> None:
    from custom_components.freshairiq.notification_policy import (
        NOTIFY_TARGET_ATTEMPTS, PUSH_RETRY_WINDOW_MIN, delivery_late, delivery_ledger, settle_delivery,
    )
    from custom_components.freshairiq.notifications import _target_identity

    data = {"notification_deliveries": {"close:bad": {"signature": "s", "accepted": ["phone"], "failed": {"tablet": 2, "notify.tablet": 1, "x": "?"},
                                                      "unavailable": {"watch": T0.isoformat()}}}}
    entry = delivery_ledger(data, "close:bad", "s", T0, _target_identity)              # written before: other spellings
    assert entry["accepted"] == ["notify.phone"] and entry["failed"] == {"notify.tablet": 2, "notify.x": 0}
    assert entry["unavailable"] == {"notify.watch": T0.isoformat()}
    assert [_target_identity(t) for t in ("phone", "notify.phone", " notify.phone ", "entity:notify.phone")] == [
        "notify.phone", "notify.phone", "notify.phone", "entity:notify.phone"]
    # the missing watch keeps the message open within the window, also after another recipient accepted it
    assert not settle_delivery(data, "close:bad", ["notify.tablet"], {"notify.x": "E"}, ["notify.watch"], T0 + timedelta(minutes=5))
    assert data["notification_deliveries"]["close:bad"]["unavailable"] == {"notify.watch": T0.isoformat()}
    for attempt in range(NOTIFY_TARGET_ATTEMPTS - 1):
        assert not settle_delivery(data, "close:bad", [], {"notify.x": "E"}, ["notify.watch"], T0 + timedelta(minutes=6 + attempt))
    # the retry limit of the broken one is reached; the watch is still waited for until the window ends
    end = T0 + timedelta(minutes=PUSH_RETRY_WINDOW_MIN)
    assert not settle_delivery(data, "close:bad", [], {}, ["notify.watch"], end)
    assert settle_delivery(data, "close:bad", [], {}, ["notify.watch"], end + timedelta(seconds=1))
    assert data["notification_deliveries"] == {}
    # a recipient no longer tried (away, filtered) is not waited for; settling without a time waits for nobody
    entry = delivery_ledger(data, "k", "s", T0, _target_identity)
    assert not settle_delivery(data, "k", ["notify.a"], {}, ["notify.b"], T0)
    assert settle_delivery(data, "k", [], {}, [], T0 + timedelta(minutes=1))
    delivery_ledger(data, "k", "s")
    assert settle_delivery(data, "k", [], {}, ["notify.b"])
    # 0.26.7.2 (owner order 21.11., third): the window counts from the first attempt; a later round, a gap without rounds or
    # another spelling never restart it or forget who got it – only a new recommendation (episode) starts over
    delivery_ledger(data, "k", "s", T0, _target_identity, "e1")
    settle_delivery(data, "k", ["notify.a"], {}, ["notify.b"], T0)
    later = delivery_ledger(data, "k", "s", T0 + timedelta(minutes=10), _target_identity, "e1")
    assert (later["accepted"], later["first_at"], delivery_late(later, T0 + timedelta(minutes=10))) == (["notify.a"], T0.isoformat(), False)
    assert not settle_delivery(data, "k", [], {}, ["notify.b"], T0 + timedelta(minutes=10))
    gap = delivery_ledger(data, "k", "s", T0 + timedelta(minutes=PUSH_RETRY_WINDOW_MIN + 1), _target_identity, "e1")
    assert gap["accepted"] == ["notify.a"] and gap["first_at"] == T0.isoformat() and delivery_late(gap, T0 + timedelta(minutes=31))
    assert settle_delivery(data, "k", [], {}, [], T0 + timedelta(minutes=PUSH_RETRY_WINDOW_MIN + 1))      # done, nobody again
    delivery_ledger(data, "k", "s", T0, _target_identity, "e1")
    settle_delivery(data, "k", ["notify.a"], {}, ["notify.b"], T0)
    fresh = delivery_ledger(data, "k", "s", T0 + timedelta(minutes=40), _target_identity, "e2")    # a new recommendation
    assert (fresh["accepted"], fresh["first_at"], fresh["episode"]) == ([], (T0 + timedelta(minutes=40)).isoformat(), "e2")
    # a ledger written before: no episode (the current one), no first attempt (its earliest time)
    data["notification_deliveries"]["old"] = {"signature": "s", "accepted": ["a"], "failed": {}, "attempt_at": (T0 + timedelta(minutes=5)).isoformat(),
                                              "unavailable": {"b": T0.isoformat()}}
    old = delivery_ledger(data, "old", "s", T0 + timedelta(minutes=6), _target_identity, "e9")
    assert (old["accepted"], old["first_at"], old["episode"]) == (["notify.a"], T0.isoformat(), "e9")
    data["notification_deliveries"]["older"] = {"signature": "s", "accepted": ["a"], "failed": {}}
    assert delivery_ledger(data, "older", "s", T0, _target_identity)["first_at"] == T0.isoformat()
