"""Locked contracts for the user-approved FreshAirIQ configuration surfaces.

These hashes intentionally make accidental edits fail the mandatory quality gate.
Update quality/ui_configuration_contract.json only when a Dashboard-settings or
Geräte-&-Dienste change has been explicitly approved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
BASELINE = json.loads((ROOT / "quality/ui_configuration_contract.json").read_text(encoding="utf-8"))
CONFIG_KEYS = ("config", "options", "config_subentries", "selector")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _canon(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dashboard_contracts() -> tuple[str, str]:
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    start = card.index("    _settingsEntryId() {")
    end = card.index("    _render() {", start)
    event_start = card.index('        this.shadowRoot.querySelectorAll("[data-settings-section]")')
    marker = "    }\n}\n\ncustomElements.define"
    event_end = card.index(marker, event_start) if marker in card[event_start:] else len(card)
    return card[start:end], card[event_start:event_end]


def _configuration_surface(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _canon({key: data[key] for key in CONFIG_KEYS})


def test_dashboard_settings_match_the_approved_baseline():
    methods, events = _dashboard_contracts()
    assert _sha(methods) == BASELINE["dashboard_settings_methods_sha256"], (
        "Dashboard-Einstellungen wurden gegenüber dem freigegebenen Stand verändert. "
        "Nur nach ausdrücklicher Freigabe den UI-Contract aktualisieren."
    )
    assert _sha(events) == BASELINE["dashboard_settings_events_sha256"], (
        "Dashboard-Einstellungsbedienung wurde gegenüber dem freigegebenen Stand verändert."
    )


def test_devices_services_schema_matches_the_approved_baseline():
    source = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert _sha(source) == BASELINE["config_flow_sha256"], (
        "Geräte-&-Dienste-Schema wurde gegenüber dem freigegebenen Stand verändert."
    )


def test_devices_services_visible_copy_matches_the_approved_baseline():
    assert _sha(_configuration_surface(COMP / "translations/de.json")) == BASELINE["de_configuration_sha256"]
    assert _sha(_configuration_surface(COMP / "translations/en.json")) == BASELINE["en_configuration_sha256"]
    assert _sha(_configuration_surface(COMP / "strings.json")) == BASELINE["strings_configuration_sha256"]


def test_german_configuration_stays_documented_and_internal_floor_ids_stay_hidden():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    blob = _canon({key: de[key] for key in CONFIG_KEYS})
    assert '"ground_floor":"Erdgeschoss"' in blob
    assert '"basement":"Kellergeschoss"' in blob
    assert "spätere FreshAirIQ-Funktionen" in blob
    assert "verändert die aktuelle Lüftungs-/ml-Empfehlung nicht" in blob
    room = de["config_subentries"]["room"]["step"]["room_basics"]
    for section in ("identity", "properties", "sensors", "geometry", "optional_sensors", "optional_actuators"):
        payload = room["sections"][section]
        assert payload.get("name") and payload.get("description")
        assert set(payload["data"]) == set(payload["data_description"])
