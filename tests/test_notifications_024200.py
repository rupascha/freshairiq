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
