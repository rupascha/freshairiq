from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            out.update(_flatten(child, path))
    else:
        out[prefix] = value
    return out


def test_four_coordinator_values_are_exported_by_status_sensor():
    sensor = (COMP / "sensor.py").read_text(encoding="utf-8")
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    for key in (
        "ventilation_threshold_mode",
        "presence_explanation",
        "pets_in_household",
        "house_strategy_samples",
    ):
        assert f'"{key}"' in coordinator
        assert f'"{key}": self.coordinator.data.get(' in sensor


def test_german_translation_is_complete_against_base_and_english():
    strings = _flatten(json.loads((COMP / "strings.json").read_text(encoding="utf-8")))
    german = _flatten(json.loads((COMP / "translations" / "de.json").read_text(encoding="utf-8")))
    english = _flatten(json.loads((COMP / "translations" / "en.json").read_text(encoding="utf-8")))
    assert set(strings) == set(german)
    assert set(english) == set(german)


def test_dashboard_settings_api_uses_the_existing_config_entry():
    api = (COMP / "feedback_api.py").read_text(encoding="utf-8")
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert "requires_auth = True" in api
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # No separate settings Store may be introduced; the API must operate on ConfigEntry.
    assert "Store(" not in api


def test_dashboard_no_longer_exposes_duplicate_integration_settings_gear():
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert 'id="settings-gear"' not in card
    assert 'data-support-open-settings=' not in card
    assert "Geräte & Dienste → FreshAirIQ → Konfigurieren" in card


# test_dashboard_settings_cover_every_native_options_key: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).


# test_settings_ui_exposes_native_room_features: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).
