"""Notification dispatch against a real Home Assistant service registry and bus."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import voluptuous as vol
from homeassistant.core import ServiceCall
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events, async_mock_service

from custom_components.freshairiq import notifications
from custom_components.freshairiq.notifications import process_notifications

NOW = datetime(2026, 9, 14, 16, 0, tzinfo=timezone.utc)  # 18:00 Berlin, outside the night window


class Store:
    def __init__(self) -> None:
        self.data: dict = {}
        self.rooms: dict = {}

    def room(self, key):
        return self.rooms.setdefault(key, {})


def _options(**overrides):
    data = {
        "notifications_enabled": True,
        "notification_targets": ["notify.phone"],
        "notification_scope": "both",
        "notification_cooldown_min": 90,
        "notification_room_keys": [],
        "notify_ventilate": True,
        "notify_close": True,
        "notify_complete": True,
        "notify_cooling": True,
        "notify_mould": True,
        "notify_sensor": True,
        "notify_night": False,
        "notify_learning": True,
        "night_start_hour": "02:00",
        "night_end_hour": "03:00",
    }
    data.update(overrides)
    return data


def _ventilate_room(key="bad", name="Bad"):
    return {"key": key, "name": name, "action": "Ventilate", "data_quality": "ok", "mould_level": "Low"}


def test_available_targets_merge_registry_and_configured_values(hass, monkeypatch) -> None:
    async_mock_service(hass, "notify", "phone")
    er.async_get(hass).async_get_or_create("notify", "demo", "tablet", suggested_object_id="tablet")
    services, entities = notifications._available_notification_targets(
        hass,
        ["entity:notify.kitchen", "notify.phone", "notify.watch", "legacy_service", "entity:light.x", "", None],
    )
    assert "phone" in services and "watch" in services and "legacy_service" in services
    assert services.count("phone") == 1
    assert "notify.kitchen" in entities and "notify.tablet" in entities
    assert "light.x" not in entities

    def _broken(_hass):
        raise AttributeError("registry not ready")

    monkeypatch.setattr(er, "async_get", _broken)
    services, entities = notifications._available_notification_targets(hass, None)
    assert "phone" in services
    assert entities == []


def test_resident_profiles_without_targets_are_ignored() -> None:
    profiles = notifications._resident_profiles({
        "resident_room_profiles": {"adult:0": {"name": "Anna"}, "adult:1": {"notification_targets": ["notify.b"]}},
        "adult_resident_names": "Anna, Ben",
    })
    assert [p["name"] for p in profiles] == ["Ben"]


def test_diagnostic_trace_recovers_from_corrupt_rows() -> None:
    store = Store()
    store.data["notification_diagnostics"] = "corrupt"
    kwargs = dict(now=NOW, event="ventilate", scope="room", status="suppressed",
                  target_count=1, available_service_count=0, reason="cooldown")
    assert notifications._record_notification_diagnostic(store, **kwargs) is True
    assert isinstance(store.data["notification_diagnostics"], list)
    # Non-dict rows are skipped; a row with a broken timestamp stops folding.
    store.data["notification_diagnostics"] = [
        {"event": "ventilate", "scope": "room", "status": "suppressed", "reason": "cooldown", "timestamp": "garbage"},
        "junk",
    ]
    assert notifications._record_notification_diagnostic(store, **kwargs) is True
    assert len(store.data["notification_diagnostics"]) == 3


async def test_room_event_routing_dedupes_resident_and_global_targets(hass) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    anna = async_mock_service(hass, "notify", "anna")
    options = _options(
        notification_scope="room",
        notification_targets=["notify.phone", "notify.anna"],
        resident_room_profiles={
            "adult:0": {"notification_targets": ["notify.anna", "notify.anna", ""], "room_keys": ["bad"]},
        },
        adult_resident_names="Anna",
    )
    store = Store()
    assert await process_notifications(hass, store, {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    await hass.async_block_till_done()
    assert len(calls) == 1  # global phone once, neutral text
    assert len(anna) == 1  # resident target deduplicated against itself and the global list
    assert store.data["notification_diagnostics"][-1]["status"] == "sent"


async def test_room_events_suppressed_failed_and_undeliverable(hass) -> None:
    events = async_capture_events(hass, "freshairiq_notification")

    # Room not selected for push.
    store = Store()
    async_mock_service(hass, "notify", "phone")
    options = _options(notification_scope="room", notification_room_keys=["other"])
    assert await process_notifications(hass, store, {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    assert store.data["notification_diagnostics"][-1]["reason"] == "room_not_selected"
    assert len(events) == 1

    # A notify service whose schema rejects the call raises synchronously.
    async def _never(call: ServiceCall) -> None:
        raise AssertionError

    hass.services.async_register(
        "notify", "strict", _never, schema=vol.Schema({vol.Required("target"): str}, extra=vol.ALLOW_EXTRA)
    )
    store = Store()
    options = _options(notification_scope="room", notification_targets=["notify.strict"])
    assert await process_notifications(hass, store, {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    row = store.data["notification_diagnostics"][-1]
    assert row["status"] == "failed" and row["exception_type"] in {"MultipleInvalid", "ServiceValidationError", "Invalid"}

    # No available service: not_sent and no cooldown mark.
    store = Store()
    options = _options(notification_scope="room", notification_targets=["notify.missing"])
    await process_notifications(hass, store, {"rooms": {"bad": _ventilate_room()}}, options, NOW, [])
    row = store.data["notification_diagnostics"][-1]
    assert row["status"] == "not_sent" and row["reason"] == "no_available_notify_service"
    assert "ventilate:bad" not in store.data.get("notifications", {})


async def test_event_bus_publication_respects_cooldown(hass) -> None:
    events = async_capture_events(hass, "freshairiq_notification")
    store = Store()
    rooms = {"bad": _ventilate_room()}
    assert notifications._publish_event(hass, store, NOW, 90, "ventilate", "T", "M", "bad", rooms, False)
    assert not notifications._publish_event(hass, store, NOW + timedelta(minutes=5), 90, "ventilate", "T", "M", "bad", rooms, False)
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_house_recommendation_recovery_grace_cooldown_and_personal_dedupe(hass) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    anna = async_mock_service(hass, "notify", "anna")
    options = _options(
        notification_scope="house",
        notification_targets=["notify.phone", "notify.anna"],
        resident_room_profiles={"adult:0": {"notification_targets": ["notify.anna", "notify.anna"], "room_keys": ["bad"]}},
        adult_resident_names="Anna",
    )

    # Sensor recommendation during start-up recovery: suppressed, signature not stored.
    store = Store()
    data = {"rooms": {}, "sensor_recovery": {"active": True},
            "intelligent_recommendation": {"kind": "sensor", "room_keys": ["bad"], "instruction": "Sensoren prüfen."}}
    await process_notifications(hass, store, data, options, NOW, [])
    assert store.data["notification_diagnostics"][-1]["reason"] == "sensor_recovery_grace"
    assert "last_house_recommendation_signature" not in store.data

    # Ventilate recommendation: Anna's phone gets the personal text once, global phone the neutral one.
    data = {"rooms": {}, "intelligent_recommendation": {"kind": "ventilate", "room_keys": ["bad"], "instruction": "Fenster öffnen."}}
    await process_notifications(hass, store, data, options, NOW, [])
    await hass.async_block_till_done()
    assert len(calls) == 1 and len(anna) == 1
    assert "one of your assigned rooms" in anna[0].data["message"]
    assert "one of your assigned rooms" not in calls[0].data["message"]
    assert store.data["notification_diagnostics"][-1]["status"] == "sent"

    # A new signature within the cooldown window is suppressed.
    data["intelligent_recommendation"] = {"kind": "ventilate", "room_keys": ["bad"], "instruction": "Weiter lüften."}
    await process_notifications(hass, store, data, options, NOW + timedelta(minutes=10), [])
    assert store.data["notification_diagnostics"][-1]["reason"] == "cooldown"
    assert len(calls) == 1


async def test_completed_session_without_valid_moisture_measurement(hass) -> None:
    calls = async_mock_service(hass, "notify", "phone")
    store = Store()
    sessions = [{"key": "bad", "name": "Bad", "removed_ml": None}]
    assert await process_notifications(hass, store, {"rooms": {}}, _options(notification_scope="room"), NOW, sessions)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert "not sufficient for a reliable final evaluation" in calls[0].data["message"]
