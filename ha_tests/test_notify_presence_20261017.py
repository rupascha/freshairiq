"""Feedback FAIQ-FB-7C943C054B43: notifications respect whether the recipient is at home.

Option ``notify_only_when_home`` (default off): a resident's own phone only gets
messages while that resident's tracker is home; general targets get nothing while
every tracker is away. ``notify_important_when_away`` (default on) still delivers
mould and sensor warnings. Unknown tracker states count as home.
"""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.freshairiq import notifications
from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.notifications import process_notifications
from ha_tests.test_cov_notifications import NOW, Store, _options, _ventilate_room

PROFILES = {
    "adult:0": {"notification_targets": ["notify.anna"], "room_keys": ["bad"]},
    "adult:1": {"notification_targets": ["notify.ben"], "room_keys": ["bad"]},
}


def _presence_options(**overrides):
    values = {
        "notification_targets": ["notify.phone"],
        "resident_room_profiles": PROFILES,
        "adult_resident_names": "Anna, Ben",
        "adult_occupants": 2,
        "adult_presence_entities": ["person.anna", "person.ben"],
    }
    values.update(overrides)
    return _options(**values)


def _services(hass):
    return {name: async_mock_service(hass, "notify", name) for name in ("anna", "ben", "phone")}


def _received(calls) -> dict[str, int]:
    return {name: len(c) for name, c in calls.items()}


def test_new_options_default_to_the_previous_behaviour() -> None:
    assert DEFAULT_OPTIONS["notify_only_when_home"] is False
    assert DEFAULT_OPTIONS["notify_important_when_away"] is True


async def test_option_off_keeps_sending_to_everyone(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "not_home")
    hass.states.async_set("person.ben", "not_home")
    assert await process_notifications(hass, Store(), {"rooms": {"bad": _ventilate_room()}}, _presence_options(), NOW, [])
    assert _received(calls) == {"anna": 1, "ben": 1, "phone": 1}


async def test_only_residents_at_home_get_the_room_message(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "not_home")
    hass.states.async_set("person.ben", "home")
    options = _presence_options(notify_only_when_home=True)
    assert await process_notifications(hass, Store(), {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    # Anna is away; Ben is home; someone is home, so the general target still gets it
    assert _received(calls) == {"anna": 0, "ben": 1, "phone": 1}


async def test_nobody_home_sends_nothing(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "not_home")
    hass.states.async_set("person.ben", "Arbeit")  # a zone name means away for person entities
    options = _presence_options(notify_only_when_home=True)
    store = Store()
    await process_notifications(hass, store, {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    assert _received(calls) == {"anna": 0, "ben": 0, "phone": 0}
    # the bus event is still fired (automations), only the phone push is held back
    rows = [r for r in store.data["notification_diagnostics"] if r.get("event") == "ventilate"]
    assert rows and rows[-1]["status"] == "not_sent" and rows[-1]["reason"] == "recipients_away"


async def test_important_warnings_still_reach_absent_residents(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "not_home")
    hass.states.async_set("person.ben", "not_home")
    options = _presence_options(notify_only_when_home=True)
    assert await notifications._send_room_personalised(hass, options, "FreshAirIQ · Bad", "Schimmelrisiko hoch.", "bad", "mould")
    assert _received(calls) == {"anna": 1, "ben": 1, "phone": 1}

    calls = _services(hass)
    options = _presence_options(notify_only_when_home=True, notify_important_when_away=False)
    assert not await notifications._send_room_personalised(hass, options, "FreshAirIQ · Bad", "Schimmelrisiko hoch.", "bad", "mould")
    assert _received(calls) == {"anna": 0, "ben": 0, "phone": 0}


async def test_unknown_tracker_counts_as_home_and_untracked_residents_follow_household(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "unavailable")
    options = _presence_options(notify_only_when_home=True, adult_presence_entities=["person.anna"])
    # Anna's tracker is unknown -> home; Ben has no tracker and follows the household (not all away)
    assert await notifications._send(hass, options, "FreshAirIQ", "Jetzt lüften.", "night")
    assert _received(calls) == {"anna": 1, "ben": 1, "phone": 1}


async def test_house_message_skips_absent_residents(hass) -> None:
    calls = _services(hass)
    hass.states.async_set("person.anna", "home")
    hass.states.async_set("person.ben", "not_home")
    options = _presence_options(notify_only_when_home=True)
    iq = {"room_keys": ["bad"], "expected_temperature_change_c": -0.5}
    assert await notifications._send_personalised(hass, options, "FreshAirIQ", "Jetzt lüften.", iq, "iq_ventilate")
    assert _received(calls) == {"anna": 1, "ben": 0, "phone": 1}


async def test_without_any_tracker_nothing_is_suppressed(hass) -> None:
    calls = _services(hass)
    options = _presence_options(notify_only_when_home=True, adult_presence_entities=[])
    assert await notifications._send(hass, options, "FreshAirIQ", "Jetzt lüften.", "night")
    assert _received(calls) == {"anna": 1, "ben": 1, "phone": 1}
