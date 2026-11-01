"""0.26.5.5 notification hotfix against a real Home Assistant service registry and bus.

F1/F2: title with the action and ordered text in German and English (event and push).
F4: the notify service is missing at the first message and registered later – the room push follows
once, the event is not repeated; residents away is a deliberate hold, not a failure.
"""
from __future__ import annotations

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_capture_events, async_mock_service

from custom_components.freshairiq.notification_policy import PUSH_PENDING
from custom_components.freshairiq.notifications import EVENT_NOTIFICATION, process_notifications
from ha_tests.test_cov_notifications import NOW, Store, _options


def _room(**extra):
    room = {"key": "bad", "name": "Bad", "action": "Ventilate", "data_quality": "ok", "mould_level": "Low",
            "recommendation_reasons": ["Raumluftfeuchte 70 % ist zu hoch (Grenze 68 %)", "Aktuell sind etwa 120 ml Feuchtigkeit entfernbar"]}
    room.update(extra)
    return room


async def test_f4_a_missing_notify_service_gets_the_push_once_it_is_registered(hass) -> None:
    hass.config.language = "de"
    events = async_capture_events(hass, EVENT_NOTIFICATION)
    store, data = Store(), {"rooms": {"bad": _room()}}
    await process_notifications(hass, store, data, _options(), NOW, [])
    await hass.async_block_till_done()
    assert len(events) == 1 and store.room("bad")[PUSH_PENDING]["action"] == "Ventilate"
    calls = async_mock_service(hass, "notify", "phone")
    for minute in (2, 3, 5):
        await process_notifications(hass, store, data, _options(), NOW + timedelta(minutes=minute), [])
        await hass.async_block_till_done()
    assert len(calls) == 1 and len(events) == 1
    assert calls[0].data["title"] == "FreshAirIQ · Bad · Jetzt lüften"
    assert calls[0].data["message"] == events[0].data["message"]
    assert calls[0].data["message"].split("\n")[1:] == ["Warum:", "• Raumluftfeuchte 70 % ist zu hoch (Grenze 68 %)",
                                                        "• Aktuell sind etwa 120 ml Feuchtigkeit entfernbar"]
    assert "\n" not in events[0].data["speech"]


async def test_f1_f2_english_push_and_event(hass) -> None:
    hass.config.language = "en"
    calls = async_mock_service(hass, "notify", "phone")
    events = async_capture_events(hass, EVENT_NOTIFICATION)
    await process_notifications(hass, Store(), {"rooms": {"bad": _room()}}, _options(), NOW, [])
    await hass.async_block_till_done()
    assert calls[0].data["title"] == events[0].data["title"] == "FreshAirIQ · Bad · Ventilate now"
    assert calls[0].data["message"].split("\n")[1:] == ["Why:", "• Room humidity 70 % is too high (limit 68 %)",
                                                        "• About 120 ml of moisture can currently be removed"]


async def test_f4_residents_away_is_a_hold_not_a_failure(hass) -> None:
    hass.config.language = "de"
    calls = async_mock_service(hass, "notify", "phone")
    hass.states.async_set("person.a", "not_home")
    store, data = Store(), {"rooms": {"bad": _room()}}
    options = _options(notify_only_when_home=True, adult_presence_entities=["person.a"])
    await process_notifications(hass, store, data, options, NOW, [])
    assert PUSH_PENDING not in store.room("bad")
    hass.states.async_set("person.a", "home")
    await process_notifications(hass, store, data, options, NOW + timedelta(minutes=2), [])
    await hass.async_block_till_done()
    assert calls == []  # no late push once they are home
