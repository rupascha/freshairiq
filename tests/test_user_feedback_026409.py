"""0.26.4.9: shutter guard over the whole airing, two-contact template guide, events for Node-RED."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

if "homeassistant" not in sys.modules:  # notifications.py only needs the HomeAssistant type
    import types as _types

    _ha = _types.ModuleType("homeassistant")
    _core = _types.ModuleType("homeassistant.core")

    class _HomeAssistant:  # pragma: no cover - type placeholder
        pass

    _core.HomeAssistant = _HomeAssistant
    _ha.core = _core
    sys.modules["homeassistant"] = _ha
    sys.modules["homeassistant.core"] = _core

from custom_components.freshairiq import cover_guard

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
T0 = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)


# --- shutter / blind guard ---------------------------------------------------------------
def _guard(closed=None, moving=False):
    affected = [{"closed_percent": closed}] if closed is not None else []
    return {"blocked": bool(affected), "affected": affected, "moving": moving, "threshold": 20.0}


def _run(pattern):
    """pattern: list of (seconds, closed_percent or None, moving)."""
    mem = {}
    cover_guard.reset(mem)
    now = T0
    for seconds, closed, moving in pattern:
        cover_guard.tick(mem, _guard(closed, moving), now)
        now += timedelta(seconds=seconds)
    cover_guard.tick(mem, _guard(None), now)
    return cover_guard.verdict(mem, 20.0)


def test_shutter_still_moving_up_after_opening_does_not_spoil_the_sample():
    # User report: window opened while the shutter was down (96 % closed), it went up
    # within seconds and stayed 90 % open for the 15-minute airing.
    result = _run([(10, 96.0, False), (10, None, True)] + [(60, None, False)] * 15)
    assert result["blocked"] is False and result["max_closed_percent"] == 96.0 and result["closed_minutes"] < 1


def test_shutter_down_for_most_of_the_airing_still_blocks_with_an_honest_message():
    result = _run([(60, 96.0, False)] * 10 + [(60, None, False)] * 5)
    assert result["blocked"] and result["closed_minutes"] == 10.0 and result["observed_minutes"] == 15.0
    text = cover_guard.diagnosis(result)
    assert "10 von 15 Minuten" in text and "bis zu 96 %" in text and "Lern-Grenze von 20 %" in text


def test_short_or_small_share_never_blocks_and_odd_timestamps_are_safe():
    assert _run([(100, 80.0, False), (60, None, False)])["blocked"] is False  # < 2 min
    assert _run([(150, 80.0, False)] + [(60, None, False)] * 10)["blocked"] is False  # < 25 %
    mem = {"session_cover_last_tick": "not a date"}
    cover_guard.tick(mem, _guard(50.0), T0)
    cover_guard.tick(mem, _guard(50.0), T0 + timedelta(hours=2))  # capped at 180 s
    assert mem["session_cover_closed_s"] == cover_guard.MAX_TICK_SECONDS
    cover_guard.tick(mem, _guard(50.0), (T0 + timedelta(hours=3)).replace(tzinfo=None))  # naive/aware mix -> 0 s
    assert mem["session_cover_closed_s"] == cover_guard.MAX_TICK_SECONDS
    assert cover_guard.verdict({}, 20.0)["blocked"] is False
    restored = {"session_cover_last_tick": T0, "session_cover_last_blocked": True}  # datetime kept in memory
    cover_guard.tick(restored, _guard(None), T0 + timedelta(seconds=30))
    assert restored["session_cover_closed_s"] == 30.0


def test_coordinator_uses_the_time_based_guard():
    text = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "cover_guard.tick(mem, cover_learning_guard, now)" in text
    assert "diagnosis = cover_guard.diagnosis(cover_session)" in text
    assert 'if state is not None and str(getattr(state, "state", "")) in {"opening", "closing"}:' in text
    assert 'mem["session_cover_learning_blocked"] = True' not in text  # the old sticky flag is gone


# --- two contacts per window: template helper instead of native pairing -------------------
def test_two_contacts_per_window_use_a_template_helper_not_a_native_pairing():
    # 0.26.4.9 (final): the native "Kippkontakt" pairing was withdrawn again on request.
    # 2-state and 3-state contacts are detected automatically as before; two binary
    # contacts are combined by a Home Assistant template helper (guide in the README).
    assert not (COMP / "tilt_pairs.py").exists()
    for name in ("coordinator.py", "config_flow.py", "strings.json", "translations/de.json", "translations/en.json"):
        text = (COMP / name).read_text(encoding="utf-8")
        assert "contact_tilt_sensors" not in text and "tilt_contact" not in text, name
    for name in ("README.md", "README_DE.md", "README_EN.md", "docs/AUTOMATIONEN.md", "docs/AUTOMATIONS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "device_class: enum" in text and "options: \"{{ ['closed', 'tilted', 'open'] }}\"" in text, name
        assert "{% elif is_state('binary_sensor." in text, name


# --- notifications: events for Node-RED / Alexa, quieter pushes ---------------------------
class _Bus:
    def __init__(self):
        self.events = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, data))


class _Services:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return domain == "notify" and service == "phone"

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data))


class _Store:
    def __init__(self):
        self.data = {}
        self.rooms = {}

    def room(self, key):
        return self.rooms.setdefault(key, {})


def _hass():
    return SimpleNamespace(services=_Services(), bus=_Bus(), config=SimpleNamespace(language="de"))


def _room(**extra):
    room = {"key": "bad", "name": "Bad", "action": "Ventilate", "data_quality": "ok", "mould_level": "Low", "surface_rh": 60,
            "recommendation_reasons": [], "configured_actuators": {"exhaust_fan": "fan.bad", "mechanical_exhaust_active": False}}
    room.update(extra)
    return room


def _options(**extra):
    options = {"notifications_enabled": False, "notification_targets": [], "notification_scope": "both", "notification_cooldown_min": 90,
               "notify_ventilate": True, "notify_close": True, "notify_mould": True, "notify_sensor": True,
               "notify_complete": True, "notify_learning": True, "notify_night": False, "night_start_hour": "22:00", "night_end_hour": "06:00"}
    options.update(extra)
    return options


def test_events_are_published_without_phone_notifications():
    from custom_components.freshairiq.notifications import EVENT_NOTIFICATION, process_notifications

    hass, store = _hass(), _Store()
    data = {"rooms": {"bad": _room()}, "intelligent_recommendation": {"kind": "ventilate", "status": "ventilate", "room_keys": ["bad"],
            "title": "Jetzt lüften", "instruction": "Fenster im Bad öffnen"}}
    asyncio.run(process_notifications(hass, store, data, _options(), T0, []))
    types = [d["type"] for e, d in hass.bus.events if e == EVENT_NOTIFICATION]
    assert types == ["ventilate", "house_ventilate"] and hass.services.calls == []
    room_event = hass.bus.events[0][1]
    assert room_event["room_key"] == "bad" and room_event["room_name"] == "Bad"
    assert "Alternativ den Lüfter einschalten." in room_event["message"] and room_event["speech"].startswith("Bad: ")
    house_event = hass.bus.events[1][1]
    assert house_event["kind"] == "ventilate" and house_event["room_keys"] == ["bad"]
    assert "Alternativ den Lüfter einschalten (Bad)." in house_event["message"]
    # same situation again: no duplicate events (cooldown / unchanged signature)
    asyncio.run(process_notifications(hass, store, data, _options(), T0 + timedelta(minutes=1), []))
    assert len(hass.bus.events) == 2


def test_running_airing_is_not_pushed_any_more_but_still_published():
    from custom_components.freshairiq.notifications import process_notifications

    hass, store = _hass(), _Store()
    data = {"rooms": {}, "intelligent_recommendation": {"kind": "continue", "status": "continue", "room_keys": ["bad"],
            "title": "Lüftung läuft", "instruction": "Lüftung weiter beobachten"}}
    asyncio.run(process_notifications(hass, store, data, _options(notifications_enabled=True, notification_targets=["notify.phone"]), T0, []))
    assert hass.services.calls == []
    assert [d["type"] for _, d in hass.bus.events] == ["house_continue"]


def test_fan_hint_only_when_a_fan_exists_and_is_off():
    from custom_components.freshairiq.notifications import _fan_hint

    assert _fan_hint(_room()) == " Alternativ den Lüfter einschalten."
    assert _fan_hint(_room(configured_actuators={"exhaust_fan": "fan.bad", "mechanical_exhaust_active": True})) == ""
    assert _fan_hint(_room(configured_actuators={})) == "" and _fan_hint({}) == ""


def test_failing_event_bus_never_breaks_notifications():
    from custom_components.freshairiq.notifications import process_notifications

    class BrokenBus:
        def async_fire(self, *_):
            raise RuntimeError("listener failed")

    hass, store = _hass(), _Store()
    hass.bus = BrokenBus()
    data = {"rooms": {"bad": _room()}}
    assert asyncio.run(process_notifications(hass, store, data, _options(), T0, [])) is True  # last_action bookkeeping


def test_night_and_session_events():
    from custom_components.freshairiq.notifications import process_notifications

    hass, store = _hass(), _Store()
    evening = datetime(2026, 10, 9, 20, 30, tzinfo=timezone.utc)
    sessions = [{"key": "bad", "name": "Bad", "learning_valid": True, "removed_ml": 120, "temp_delta_c": -0.8, "cost": 0.03}]
    data = {"rooms": {}, "night_strategy": {"action": "close", "instruction": "Fenster nachts geschlossen lassen"}, "overnight_forecast_ml": 80}
    asyncio.run(process_notifications(hass, store, data, _options(), evening, sessions))
    types = [d["type"] for _, d in hass.bus.events]
    assert types == ["learning", "complete", "night"]
    assert hass.bus.events[2][1]["kind"] == "close" and "Fenster nachts geschlossen lassen" in hass.bus.events[2][1]["message"]
    asyncio.run(process_notifications(hass, store, data, _options(), evening + timedelta(minutes=5), []))
    assert len(hass.bus.events) == 3  # once per evening


def test_automation_docs_explain_the_event_for_node_red():
    for name, words in (("docs/AUTOMATIONEN.md", ("freshairiq_notification", "Node-RED", "Alexa")), ("docs/AUTOMATIONS.md", ("freshairiq_notification", "Node-RED", "Alexa"))):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert all(word in text for word in words), name
