from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # pragma: no cover - type placeholder only
        pass

    core.HomeAssistant = HomeAssistant
    ha.core = core
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core

from custom_components.freshairiq.notifications import (
    _all_notification_targets,
    _has_notification_targets,
    _send_room_personalised,
)
from custom_components.freshairiq.presence import resolve_occupancy


class _Services:
    def __init__(self):
        self.calls = []

    def has_service(self, domain, service):
        return domain == "notify" and service in {"paul", "lydia", "house"}

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class _Hass:
    def __init__(self):
        self.services = _Services()


class _State:
    def __init__(self, state):
        self.state = state


def _resident_options():
    return {
        "notification_targets": [],
        "resident_room_profiles": {
            "adult:0": {
                "name": "Paul",
                "room_keys": ["office"],
                "thermal_preference": "balanced",
                "notification_targets": ["notify.paul"],
            },
            "adult:1": {
                "name": "Lydia",
                "room_keys": ["bedroom"],
                "thermal_preference": "balanced",
                "notification_targets": ["notify.lydia"],
            },
        },
    }


def test_personal_targets_count_without_global_targets():
    options = _resident_options()
    assert _has_notification_targets(options) is True
    assert _all_notification_targets(options) == ["notify.paul", "notify.lydia"]


def test_personal_and_global_targets_are_deduplicated():
    options = _resident_options()
    options["notification_targets"] = ["notify.house", "notify.paul"]
    assert _all_notification_targets(options) == ["notify.house", "notify.paul", "notify.lydia"]


def test_room_notification_only_reaches_assigned_resident_plus_global_targets():
    options = _resident_options()
    options["notification_targets"] = ["notify.house"]
    hass = _Hass()

    sent = asyncio.run(
        _send_room_personalised(
            hass, options, "FreshAirIQ · Arbeitszimmer", "Jetzt lüften.", "office"
        )
    )

    assert sent is True
    services = [call[1] for call in hass.services.calls]
    assert services == ["paul", "house"]
    assert hass.services.calls[0][2]["message"].startswith("Paul, ")
    assert hass.services.calls[1][2]["message"] == "Jetzt lüften."


def test_pet_safe_sensor_is_effective_without_duplicate_general_selection():
    states = {
        "person.a": _State("not_home"),
        "binary_sensor.pet_safe": _State("on"),
    }
    options = {
        "adult_occupants": 2,
        "child_occupants": 0,
        "adult_presence_entities": ["person.a"],
        "child_presence_entities": [],
        "presence_sensor_entities": [],
        "pet_safe_presence_entities": ["binary_sensor.pet_safe"],
        "pets_in_household": True,
        "untracked_follow_household": True,
    }
    result = resolve_occupancy(options, states.get)
    assert "binary_sensor.pet_safe" in result["active_presence_sensors"]
    assert result["expected_total"] > 0


def test_frontend_hotfix_contracts_present():
    js = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert 'const FAIQ_VERSION = "0.25.0.58";' in js
    assert '["group_basics","mdi:home-outline","Grundlagen"' in js
    assert '["building","mdi:home-city-outline","Gebäude"]' in js
    assert 'if (name === "building")' in js
    assert '["residents", "house", "personalisation"].includes(name)' in js
    assert 'PERSÖNLICHES IQ-PROFIL' in js
    assert 'a.freshairiq_entity_key === key' in js
    assert 'await this._settingsPost({ action: scope === "data" ? "set_data" : "set_option", key, value }, true);' in js
