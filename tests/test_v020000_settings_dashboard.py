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
    api = (COMP / "settings_api.py").read_text(encoding="utf-8")
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert 'url = "/api/freshairiq/settings/{entry_id}"' in api
    assert "requires_auth = True" in api
    assert "async_update_entry(entry, options=options)" in api
    assert "async_update_entry(entry, data=data)" in api
    assert "FreshAirIQSettingsView" in init
    assert "register_view(FreshAirIQSettingsView())" in init
    # No separate settings Store may be introduced; the API must operate on ConfigEntry.
    assert "Store(" not in api


def test_dashboard_has_settings_gear_and_full_category_navigation():
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert 'id="settings-gear"' in card
    for text in (
        "Außenluft & Wetter",
        "Gebäude",
        "Bewohnerprofil",
        "Stockwerke & Bereiche",
        "Räume & Sensoren",
        "Betriebsprofil",
        "Prognose",
        "Optionale Sensoren & Außenluft",
        "Querlüftung",
        "Lüftungsmodell",
        "Energie & Kosten",
        "Benachrichtigungen",
        "Daten & Statistik",
        "Wartung",
    ):
        assert text in card
    assert "Standard:" in card
    assert "wohnzimmer+schlafzimmer" in card
    assert "wohnzimmer+fitnessraum" in card


def test_dashboard_settings_cover_every_native_options_key():
    api = (COMP / "settings_api.py").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    # These are the values exposed by the native Devices & Services option forms.
    native_keys = {
        "start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh", "close_delta",
        "threshold_mode", "min_potential_percent_total_water", "min_potential_total_ml", "min_potential_room_ml",
        "min_duration_min", "max_duration_min", "post_ventilation_stabilization_min",
        "repeat_recommendation_cooldown_min", "repeat_min_benefit_ml", "min_return_next_5_min_ml",
        "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c", "surface_factor",
        "mould_warn_surface_rh", "mould_critical_surface_rh", "co2_warn", "co2_critical",
        "learning_enabled", "learning_max_duration_min", "cross_ventilation_pairs", "cross_zone_connections",
        "operating_profile", "cooling_start_temp_c", "cooling_min_outdoor_delta_c", "cooling_max_indoor_rh",
        "cooling_max_moisture_gain_5min_ml", "forecast_horizon_min", "pollen_enabled", "pollen_max",
        "pollen_strict_veto", "wind_orientation_enabled", "property_type", "adult_occupants", "child_occupants",
        "adult_presence_entities", "child_presence_entities", "presence_sensor_entities", "pet_safe_presence_entities",
        "pets_in_household", "untracked_follow_household", "night_start_hour", "night_end_hour",
        "night_forecast_enabled", "heating_system", "electricity_price_per_kwh", "heat_pump_cop",
        "gas_price_per_kwh", "gas_efficiency", "district_price_per_kwh", "district_efficiency",
        "oil_price_per_liter", "oil_kwh_per_liter", "oil_efficiency", "notifications_enabled",
        "notification_targets", "notification_scope", "notification_room_keys", "notify_ventilate", "notify_close",
        "notify_complete", "notify_cooling", "notify_mould", "notify_sensor", "notify_night", "notify_learning",
        "notification_cooldown_min", "statistics_days",
    }
    # settings_api imports the canonical native key contract rather than
    # duplicating every literal key in a second hand-maintained set.
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert "EDITABLE_OPTION_KEYS = set(NATIVE_OPTION_KEYS)" in api
    for key in native_keys:
        assert f'"{key}"' in flow, key
        assert f'key:"{key}"' in card, key
    for key in ("outdoor_weather", "outdoor_temperature", "outdoor_humidity", "pollen_entity"):
        assert f'key:"{key}"' in card


def test_settings_ui_exposes_native_room_features():
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    api = (COMP / "settings_api.py").read_text(encoding="utf-8")
    for marker in (
        "room-temp", "room-humidity", "room-contacts", "room-contact-mode", "room-volume",
        "room-length", "room-width", "room-height", "room-ref-temp", "room-ref-humidity",
        "room-co2", "room-sources", "room-contact-orientation", "room-contact-delay",
        "settings-save-levels", "delete_room", "reorder_rooms",
    ):
        assert marker in card or marker in api
