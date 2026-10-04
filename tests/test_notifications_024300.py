"""Deep notification-orchestrator hardening for FreshAirIQ 0.25.0.7."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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

from custom_components.freshairiq.notifications import _continuation, _finite_float, process_notifications


class Services:
    def __init__(self, available=("phone",)):
        self.available = set(available)
        self.calls = []
    def has_service(self, domain, service):
        return domain == "notify" and service in self.available
    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class Hass:
    def __init__(self, available=("phone",)):
        self.services = Services(available)


class Store:
    def __init__(self):
        self.data = {}
        self.rooms = {}
    def room(self, key):
        return self.rooms.setdefault(key, {})


def base_options(**overrides):
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
        "night_start_hour": "22:00",
        "night_end_hour": "07:00",
    }
    data.update(overrides)
    return data


def test_finite_float_and_continuation_reject_nonfinite_values():
    assert _finite_float("bad", 7) == 7
    assert _finite_float(float("nan"), 8) == 8
    assert _finite_float(float("inf"), 9) == 9
    text = _continuation({
        "forecast_horizon_min": float("nan"),
        "forecast_moisture_effect_ml": float("inf"),
        "forecast_temperature_change_c": "broken",
        "forecast_cost": -5,
    })
    assert "Weitere 5 Min" in text
    assert "±0 ml" in text
    assert "±0.0 °C" in text
    assert "0.00 €" in text


def test_process_notifications_disabled_or_without_targets_is_noop():
    now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    assert asyncio.run(process_notifications(Hass(), Store(), {}, base_options(notifications_enabled=False), now, [])) is False
    assert asyncio.run(process_notifications(Hass(), Store(), {}, base_options(notification_targets=[]), now, [])) is False


def test_room_notifications_cover_all_transitions_and_corrupt_rooms():
    hass, store = Hass(), Store()
    now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    rooms = {
        "v": {"key":"v","name":"Bad","action":"Ventilate","data_quality":"ok","mould_level":"Low","recommendation_reasons":["Feuchte"]},
        "c": {"key":"c","name":"Wohnen","action":"Ventilate for cooling","data_quality":"ok","mould_level":"Low","forecast_horizon_min":10},
        "x": {"key":"x","name":"Schlafzimmer","action":"Close","data_quality":"ok","mould_level":"Low","forecast_horizon_min":5},
        "m": {"key":"m","name":"Keller","action":"Wait","data_quality":"ok","mould_level":"High","surface_rh":82.4},
        "s": {"key":"s","name":"Büro","action":"Wait","data_quality":"stale","mould_level":"Low"},
        "broken": "not-a-room",
    }
    data = {"rooms": rooms, "intelligent_recommendation": {}}
    assert asyncio.run(process_notifications(hass, store, data, base_options(notification_scope="room"), now, []))
    messages = "\n".join(c[2]["message"] for c in hass.services.calls)
    assert "Jetzt lüften" in messages
    assert "Sommerkühlung sinnvoll" in messages
    assert "jetzt schließen" in messages
    assert "Schimmelrisiko high" in messages
    assert "Sensoren prüfen" in messages
    first_count = len(hass.services.calls)
    # Persisted transition + cooldown prevent a restart-style notification storm.
    asyncio.run(process_notifications(hass, store, data, base_options(notification_scope="room"), now, []))
    assert len(hass.services.calls) == first_count


def test_house_recommendation_signature_personalisation_and_failed_delivery():
    now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    store = Store()
    options = base_options(notification_scope="house")
    data = {"rooms": {}, "intelligent_recommendation": {
        "kind":"ventilate", "title":"Lüften", "instruction":"Fenster öffnen.",
        "summary":"Gute Außenluft.", "reasons":["Delta hoch", "CO₂"], "secondary":"10 Minuten", "room_keys":["living"],
    }}
    hass = Hass()
    assert asyncio.run(process_notifications(hass, store, data, options, now, []))
    assert len(hass.services.calls) == 1
    assert store.data["last_house_recommendation_signature"].startswith("ventilate:")
    # Same signature is remembered and not resent.
    asyncio.run(process_notifications(hass, store, data, options, now, []))
    assert len(hass.services.calls) == 1

    # No valid notify service: signature must not be committed, so a later retry remains possible.
    failed_store = Store()
    failed = Hass(available=())
    changed = asyncio.run(process_notifications(failed, failed_store, data, options, now, []))
    assert changed is True  # privacy-safe failed-delivery diagnostics are persisted
    assert failed_store.data["notification_diagnostics"][-1]["status"] == "not_sent"
    assert "last_house_recommendation_signature" not in failed_store.data


def test_learning_completion_and_malformed_sessions_degrade_safely():
    hass, store = Hass(), Store()
    now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    sessions = [
        None,
        {},
        {"key":"bad","name":"Bad","learning_valid":True,"removed_ml":float("nan"),"temp_delta_c":float("inf"),"cost":"broken"},
    ]
    changed = asyncio.run(process_notifications(hass, store, {"rooms":{}}, base_options(notification_scope="room"), now, sessions))
    assert changed
    text = "\n".join(c[2]["message"] for c in hass.services.calls)
    assert "Lernprobe" in text
    assert "0 ml entfernt" in text
    assert "+0.0 °C" in text
    assert "0.00 €" in text


def test_night_strategy_open_closed_and_fallback_paths():
    options = base_options(notification_scope="house", notify_ventilate=False, notify_night=True, night_start_hour="22:00")
    now = datetime(2026, 9, 14, 20, 30, tzinfo=timezone.utc)
    variants = [
        {"night_strategy":{"action":"open_selected","forecast_without_action_ml":100,"forecast_with_strategy_ml":-30,"instruction":"Öffnen","summary":"Kühl und trocken"}},
        {"night_strategy":{"action":"keep_closed","forecast_without_action_ml":50,"instruction":"Geschlossen lassen"}},
        {"night_strategy":{"instruction":"Beobachten"},"overnight_forecast_ml":float("nan")},
    ]
    for data in variants:
        hass, store = Hass(), Store()
        assert asyncio.run(process_notifications(hass, store, {"rooms":{}, **data}, options, now, []))
        assert store.data["last_night_notification_date"] == "2026-09-14"
        assert len(hass.services.calls) == 1


def test_invalid_night_start_and_non_dict_payloads_do_not_crash():
    hass, store = Hass(), Store()
    now = datetime(2026, 9, 14, 20, 0, tzinfo=timezone.utc)
    options = base_options(notification_scope="house", notify_ventilate=False, notify_night=True, night_start_hour="broken")
    data = {"rooms": [], "intelligent_recommendation": "broken", "night_strategy": "broken", "overnight_forecast_ml": "bad"}
    assert asyncio.run(process_notifications(hass, store, data, options, now, []))


def test_night_suppression_blocks_all_pushes_but_consumes_action_transition():
    hass, store = Hass(), Store()
    night = datetime(2026, 9, 14, 23, 15, tzinfo=timezone.utc)
    options = base_options(
        notification_scope="both",
        suppress_notifications_at_night=True,
        night_forecast_enabled=True,
        night_start_hour="22:00",
        night_end_hour="07:00",
        notify_night=True,
    )
    data = {
        "rooms": {"v": {"key":"v","name":"Bad","action":"Ventilate","data_quality":"ok","mould_level":"Low","recommendation_reasons":["Feuchte"]}},
        "intelligent_recommendation": {"kind":"ventilate","title":"Lüften","instruction":"Fenster öffnen.","summary":"Gute Außenluft.","room_keys":["v"]},
        "night_strategy": {"action":"open_selected","forecast_without_action_ml":100,"forecast_with_strategy_ml":-20,"instruction":"Öffnen"},
    }
    assert asyncio.run(process_notifications(hass, store, data, options, night, []))
    assert hass.services.calls == []
    assert store.room("v")["last_action"] == "Ventilate"
    assert store.data["last_house_recommendation_signature"].startswith("ventilate:")
    assert "last_night_notification_date" not in store.data

    # The already-consumed night transition must not create a catch-up storm after quiet hours.
    morning = datetime(2026, 9, 15, 7, 1, tzinfo=timezone.utc)
    asyncio.run(process_notifications(hass, store, data, options, morning, []))
    assert hass.services.calls == []


def test_night_suppression_respects_switch_night_feature_and_boundaries():
    data = {"rooms": {"v": {"key":"v","name":"Bad","action":"Ventilate","data_quality":"ok","mould_level":"Low","recommendation_reasons":["Feuchte"]}}}
    # Exactly at start is quiet.
    hass, store = Hass(), Store()
    opts = base_options(notification_scope="room", suppress_notifications_at_night=True, night_forecast_enabled=True)
    asyncio.run(process_notifications(hass, store, data, opts, datetime(2026,9,14,22,0,tzinfo=timezone.utc), []))
    assert hass.services.calls == []
    # Exactly at end is no longer quiet.
    hass, store = Hass(), Store()
    asyncio.run(process_notifications(hass, store, data, opts, datetime(2026,9,15,7,0,tzinfo=timezone.utc), []))
    assert len(hass.services.calls) == 1
    # User can leave suppression disabled.
    hass, store = Hass(), Store()
    opts = base_options(notification_scope="room", suppress_notifications_at_night=False, night_forecast_enabled=True)
    asyncio.run(process_notifications(hass, store, data, opts, datetime(2026,9,14,23,0,tzinfo=timezone.utc), []))
    assert len(hass.services.calls) == 1
    # Night feature off means the quiet-hours coupling is inactive.
    hass, store = Hass(), Store()
    opts = base_options(notification_scope="room", suppress_notifications_at_night=True, night_forecast_enabled=False)
    asyncio.run(process_notifications(hass, store, data, opts, datetime(2026,9,14,23,0,tzinfo=timezone.utc), []))
    assert len(hass.services.calls) == 1


def test_coordinator_never_short_circuits_notification_processing():
    """Regression: pending state changes must not skip process_notifications."""
    from pathlib import Path
    source = (Path(__file__).parents[1] / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "notification_changed = await process_notifications(" in source
    assert "changed = changed or await process_notifications(" not in source


def test_notification_delivery_diagnostics_are_privacy_safe_and_bounded():
    now = datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc)
    store = Store()
    data = {"rooms": {}, "intelligent_recommendation": {
        "kind": "close", "title": "Close", "instruction": "Close now", "summary": "Done", "room_keys": ["bedroom"]
    }}
    failed = Hass(available=())
    changed = asyncio.run(process_notifications(failed, store, data, base_options(notification_scope="house"), now, []))
    assert changed is True  # diagnostic trace itself must be persisted
    trace = store.data["notification_diagnostics"]
    assert trace[-1]["status"] == "not_sent"
    assert trace[-1]["reason"] == "no_available_notify_service"
    assert trace[-1]["target_count"] == 1
    assert trace[-1]["available_service_count"] == 0
    serialised = str(trace[-1])
    assert "notify.phone" not in serialised
    assert "Close now" not in serialised


def test_notification_delivery_diagnostics_capture_exception_type_without_message():
    class FailingServices(Services):
        async def async_call(self, domain, service, data, blocking=False):
            raise RuntimeError("secret device detail")
    hass = Hass()
    hass.services = FailingServices()
    store = Store()
    now = datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc)
    data = {"rooms": {}, "intelligent_recommendation": {
        "kind": "close", "title": "Close", "instruction": "Close now", "summary": "Done", "room_keys": []
    }}
    assert asyncio.run(process_notifications(hass, store, data, base_options(notification_scope="house"), now, []))
    row = store.data["notification_diagnostics"][-1]
    assert row["status"] == "failed"
    assert row["exception_type"] == "RuntimeError"
    assert "secret device detail" not in str(row)


def test_modern_notify_entity_uses_send_message_target_contract():
    from custom_components.freshairiq.notifications import _send_targets

    class States:
        def get(self, entity_id):
            return object() if entity_id == "notify.sweethome" else None

    hass = Hass(available=("send_message",))
    hass.states = States()
    sent = asyncio.run(_send_targets(
        hass, ["entity:notify.sweethome"], "FreshAirIQ · Test", "Hallo"
    ))
    assert sent is True
    assert hass.services.calls == [(
        "notify", "send_message",
        {"message": "Hallo", "target": {"entity_id": "notify.sweethome"}, "title": "FreshAirIQ · Test"},
        False,
    )]


def test_modern_notify_entity_is_not_sent_when_entity_is_missing():
    from custom_components.freshairiq.notifications import _send_targets

    class States:
        def get(self, _entity_id):
            return None

    hass = Hass(available=("send_message",))
    hass.states = States()
    assert asyncio.run(_send_targets(hass, ["entity:notify.missing"], "Test", "Hallo")) is False
    assert hass.services.calls == []
