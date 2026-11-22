"""Notification routing hardening without a Home Assistant runtime."""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import sys
import types

if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    class HomeAssistant:  # pragma: no cover
        pass
    core.HomeAssistant = HomeAssistant
    ha.core = core
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core

from custom_components.freshairiq.notifications import (
    _all_notification_targets,
    _allowed_room,
    _due,
    _has_notification_targets,
    _mark_sent,
    _resident_profiles,
    _send_personalised,
    _send_room_personalised,
    _send_targets,
    _target_service,
)


class _Services:
    def __init__(self, available=()):
        self.available = set(available)
        self.calls = []
    def has_service(self, domain, service):
        return domain == "notify" and service in self.available
    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))

class _Hass:
    def __init__(self, available=()):
        self.services = _Services(available)

class _Store:
    def __init__(self):
        self.data = {}


def test_notification_target_normalisation_and_corrupt_profiles():
    assert _target_service("notify.mobile_app_phone") == "mobile_app_phone"
    assert _target_service("mobile_app_phone") == "mobile_app_phone"
    assert _resident_profiles({"resident_room_profiles": "[]"}) == []
    assert _resident_profiles({"resident_room_profiles": "not-json"}) == []
    options = {
        "notification_targets": ["notify.a", "notify.a", ""],
        "resident_room_profiles": {"p": {"notification_targets": ["notify.b", "notify.a"]}},
    }
    assert _all_notification_targets(options) == ["notify.a", "notify.b"]
    assert _has_notification_targets(options)
    assert not _has_notification_targets({})


def test_notification_room_filter_and_cooldown_handles_legacy_timestamp():
    assert _allowed_room("a", {})
    assert _allowed_room("a", {"notification_room_keys": ["a"]})
    assert not _allowed_room("b", {"notification_room_keys": ["a"]})
    store = _Store()
    now = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)
    assert _due(store, "x", now, 90)
    _mark_sent(store, "x", now)
    assert not _due(store, "x", now, 90)
    store.data["notifications"]["legacy"] = "2026-09-14T07:00:00"  # naive legacy timestamp
    assert _due(store, "legacy", now, 90)  # mismatch must degrade safely, never crash
    store.data["notifications"]["broken"] = "not-a-date"
    assert _due(store, "broken", now, 90)


def test_send_targets_deduplicates_and_skips_unknown_services():
    hass = _Hass({"a"})
    sent = asyncio.run(_send_targets(hass, ["notify.a", "notify.a", "notify.missing", ""], "T", "M"))
    assert sent is True
    assert len(hass.services.calls) == 1
    assert hass.services.calls[0][1] == "a"


def test_room_personalised_routing_avoids_duplicate_global_delivery():
    hass = _Hass({"paul", "global"})
    options = {
        "resident_room_profiles": {"p": {"name": "Paul", "room_keys": ["living"], "notification_targets": ["notify.paul"]}},
        "notification_targets": ["notify.paul", "notify.global"],
    }
    assert asyncio.run(_send_room_personalised(hass, options, "T", "Lüften", "living"))
    assert [c[1] for c in hass.services.calls] == ["paul", "global"]
    assert hass.services.calls[0][2]["message"].startswith("Paul, ")


def test_personalised_message_respects_room_and_thermal_context():
    hass = _Hass({"paul", "global"})
    options = {
        "resident_room_profiles": {"p": {
            "name": "Paul", "room_keys": ["living"], "thermal_preference": "warm",
            "notification_targets": ["notify.paul"],
        }},
        "notification_targets": ["notify.global"],
    }
    iq = {"room_keys": ["living"], "expected_temperature_change_c": -0.8}
    assert asyncio.run(_send_personalised(hass, options, "T", "Fenster öffnen.", iq))
    personal = hass.services.calls[0][2]["message"]
    assert "hinterlegten Räume" in personal
    assert "warmes Komfortprofil" in personal


# 0.26.7.2 (support diagnosis 21.11.): residents sharing one phone, one of them away. Who may get the message is decided per
# profile first; the recipients are merged afterwards by the service they reach (notify.phone is phone).
import pytest  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from custom_components.freshairiq.notifications import _send  # noqa: E402


class _PresenceHass(_Hass):
    def __init__(self, available=(), states=None):
        super().__init__(available)
        self.states = SimpleNamespace(get=lambda entity_id: SimpleNamespace(state=(states or {})[entity_id]) if entity_id in (states or {}) else None)


def _shared(order, *, anna="not_home", ben="home", anna_targets=("notify.phone",), ben_targets=("phone",), rooms=("bad",)):
    profiles = {
        "adult:0": {"name": "Anna", "room_keys": list(rooms), "notification_targets": list(anna_targets)},
        "adult:1": {"name": "Ben", "room_keys": list(rooms), "notification_targets": list(ben_targets)},
    }
    options = {"notify_only_when_home": True, "adult_presence_entities": ["person.anna", "person.ben"],
               "adult_resident_names": "Anna, Ben", "notification_targets": [],
               "resident_room_profiles": {slot: profiles[slot] for slot in order}}
    return _PresenceHass({"phone", "tablet"}, {"person.anna": anna, "person.ben": ben}), options


ORDERS = [("adult:0", "adult:1"), ("adult:1", "adult:0")]
SENDERS = {
    "room": lambda hass, options, event=None: _send_room_personalised(hass, options, "T", "Lüften", "bad", event),
    "house": lambda hass, options, event=None: _send_personalised(hass, options, "T", "Lüften", {"room_keys": ["bad"]}, event),
    "household": lambda hass, options, event=None: _send(hass, options, "T", "Lüften", event),
}


@pytest.mark.parametrize("ben_targets", [("notify.phone",), ("phone",)], ids=["same_spelling", "service_name"])
@pytest.mark.parametrize("scope", list(SENDERS))
@pytest.mark.parametrize("order", ORDERS, ids=["away_first", "home_first"])
def test_shared_target_reaches_the_present_resident_whatever_the_order(scope, order, ben_targets):
    hass, options = _shared(order, ben_targets=ben_targets)
    assert asyncio.run(SENDERS[scope](hass, options))
    assert [call[1] for call in hass.services.calls] == ["phone"]
    if scope != "household":
        assert hass.services.calls[0][2]["message"].startswith("Ben, ")


@pytest.mark.parametrize("scope", list(SENDERS))
@pytest.mark.parametrize("order", ORDERS, ids=["anna_first", "ben_first"])
def test_shared_target_of_absent_residents_only_gets_nothing(scope, order):
    hass, options = _shared(order, ben="not_home")
    options["notification_targets"] = ["notify.phone"]  # the shared phone also as a global target: the household is away
    assert not asyncio.run(SENDERS[scope](hass, options))
    assert hass.services.calls == []


@pytest.mark.parametrize("scope", list(SENDERS))
def test_an_absent_residents_own_phone_stays_quiet_and_important_events_go_out(scope):
    hass, options = _shared(ORDERS[0], ben_targets=("tablet",))
    options["notification_targets"] = ["phone"]  # Anna's phone as a global target while Ben is at home
    assert asyncio.run(SENDERS[scope](hass, options))
    assert [call[1] for call in hass.services.calls] == ["tablet"]
    hass, options = _shared(ORDERS[0], ben_targets=("tablet",))
    assert asyncio.run(SENDERS[scope](hass, options, "mould"))  # important while away: everyone, once each
    assert sorted(call[1] for call in hass.services.calls) == ["phone", "tablet"]


@pytest.mark.parametrize("scope", list(SENDERS))
def test_a_notify_entity_is_its_own_recipient(scope):
    hass, options = _shared(ORDERS[0], anna="home", anna_targets=("entity:notify.phone",), ben_targets=("notify.phone", "phone"))
    hass.services.available.add("send_message")
    hass.states = SimpleNamespace(get=lambda entity_id: SimpleNamespace(state="home"))
    assert asyncio.run(SENDERS[scope](hass, options))
    assert sorted(call[1] for call in hass.services.calls) == ["phone", "send_message"]
    entity = next(call for call in hass.services.calls if call[1] == "send_message")
    assert entity[2]["entity_id"] == "notify.phone"


def test_the_room_filter_of_a_profile_still_applies():
    hass, options = _shared(ORDERS[0], anna="home", rooms=("kueche",))
    assert not asyncio.run(_send_room_personalised(hass, options, "T", "Lüften", "bad"))
    assert hass.services.calls == []
    options["resident_room_profiles"]["adult:1"]["room_keys"] = ["bad"]
    assert asyncio.run(_send_room_personalised(hass, options, "T", "Lüften", "bad"))
    assert [call[2]["message"] for call in hass.services.calls] == ["Ben, Lüften"]
