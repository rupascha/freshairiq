"""Regression contracts for FreshAirIQ 0.25.0.7 start-forecast/settings hotfix."""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

from custom_components.freshairiq.forecast_validation import (
    evaluate_start_forecast_at_duration,
    freeze_start_forecast_context,
)
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _context():
    args = {
        "current_ah": 13.0,
        "source_ah": 8.0,
        "current_temp_c": 22.0,
        "source_temp_c": 12.0,
        "volume_m3": 50.0,
        "rate_per_min": 0.035,
        "airflow_bonus": 1.0,
        "prior_source_ml_min": 0.5,
        "learned_source_ml_min": 0.2,
        "learned_thermal_residual_c_min": 0.0,
        "observation_samples": 4,
        "model_maturity_pct": 70.0,
        "future_source_boundaries": {
            5: {"absolute_humidity": 8.0, "temperature_c": 12.0},
            10: {"absolute_humidity": 8.2, "temperature_c": 12.4},
        },
    }
    options = {
        "min_return_next_5_min_ml": 25.0,
        "max_temp_loss_next_5_min_c": 0.6,
        "min_efficiency_ml_per_01c": 8.0,
        "min_duration_min": 3.0,
        "max_duration_min": 20.0,
        "operating_profile": "comfort",
        "heating_system": "gas",
        "electricity_price_per_kwh": 0.30,
        "heat_pump_cop": 3.5,
        "gas_price_per_kwh": 0.11,
        "gas_efficiency": 0.92,
        "district_price_per_kwh": 0.15,
        "district_efficiency": 0.98,
        "oil_price_per_liter": 1.0,
        "oil_kwh_per_liter": 10.0,
        "oil_efficiency": 0.88,
    }
    return freeze_start_forecast_context(
        args,
        target_ah=10.5,
        options=options,
        start_ah=13.0,
        start_source_ah=8.0,
        start_temp_c=22.0,
        start_source_temp_c=12.0,
    )


def test_start_curve_replays_same_frozen_start_at_real_duration():
    context = _context()
    at_5 = evaluate_start_forecast_at_duration(context, 5.0)
    at_23 = evaluate_start_forecast_at_duration(context, 23.0)
    assert at_5 and at_23
    assert at_5["duration_min"] == 5.0
    assert at_23["duration_min"] == 23.0
    assert at_5["predicted_removed_ml"] != at_23["predicted_removed_ml"]
    # Replaying a later point must not mutate the frozen start state.
    assert context["forecast_args"]["current_ah"] == 13.0
    assert context["forecast_args"]["running"] is False
    assert context["forecast_args"]["session_elapsed_min"] == 0.0


def test_start_curve_survives_json_store_roundtrip():
    context = json.loads(json.dumps(_context()))
    # JSON turns integer future-weather keys into strings; replay normalises them.
    assert "5" in context["forecast_args"]["future_source_boundaries"]
    result = evaluate_start_forecast_at_duration(context, 10.0)
    assert result is not None
    assert result["duration_min"] == 10.0


def test_result_shows_time_aligned_comparison_without_learning_from_held_frames():
    group = {
        "started_at": "2026-09-14T17:00:00+02:00",
        "sessions": [{
            "key": "wohnkuche",
            "name": "Wohnküche",
            "sort_order": 1,
            "volume_m3": 85.8,
            "started_at": "2026-09-14T17:00:00+02:00",
            "ended_at": "2026-09-14T17:25:00+02:00",
            "removed_ml": 100.0,
            "duration_min": 25.0,
            "temp_delta_c": -0.5,
            "cost": 0.02,
            "energy_kwh": 0.1,
            "predicted_removed_ml": 80.0,
            "predicted_temperature_change_c": -0.4,
            "prediction_time_aligned": True,
            "prediction_comparable": False,
            "learning_valid": False,
            "outcome_feedback_action": "skipped",
            "outcome_feedback_reason": "Sensortakt nicht ausreichend synchronisiert",
        }],
    }
    result = finalise_ventilation_group(group, ended_at=__import__("datetime").datetime.fromisoformat("2026-09-14T17:25:00+02:00"))
    assert result is not None
    assert result["predicted_removed_ml"] is None  # strict objective score unchanged
    assert result["aligned_predicted_removed_ml"] == 80
    assert result["aligned_prediction_actual_removed_ml"] == 100
    assert result["aligned_prediction_accuracy_percent"] is None
    assert result["prediction_time_aligned_rooms"] == 1
    assert result["prediction_comparable_rooms"] == 0
    assert result["prediction_alignment_quality"] == "informational"
    assert "nicht ausreichend synchron" in result["prediction_status_text"]


def test_result_marks_clean_aligned_comparison_as_validated():
    group = {
        "started_at": "2026-09-14T17:00:00+02:00",
        "sessions": [{
            "key": "bad",
            "name": "Bad",
            "volume_m3": 30.0,
            "started_at": "2026-09-14T17:00:00+02:00",
            "ended_at": "2026-09-14T17:10:00+02:00",
            "removed_ml": 45.0,
            "duration_min": 10.0,
            "temp_delta_c": -0.2,
            "predicted_removed_ml": 50.0,
            "prediction_time_aligned": True,
            "prediction_comparable": True,
        }],
    }
    result = finalise_ventilation_group(group, ended_at=__import__("datetime").datetime.fromisoformat("2026-09-14T17:10:00+02:00"))
    assert result["predicted_removed_ml"] == 50
    assert result["aligned_predicted_removed_ml"] == 50
    assert result["prediction_comparable_rooms"] == 1
    assert result["prediction_alignment_quality"] == "validated"


def test_coordinator_uses_logical_measurement_start_and_replays_actual_measurement_duration():
    source = (COMP / "coordinator.py").read_text(encoding="utf-8")
    capture = source[source.index("# Hotfix 0.24.14.1: freeze"):source.index("# Validation Engine v2:")]
    finish = source[source.index("# Hotfix 0.24.14.1: compare"):source.index("event_id =", source.index("# Hotfix 0.24.14.1: compare"))]
    assert "measurement_elapsed_now <= 2.5" in capture
    assert 'and measurement_frame.get("validation_eligible")' not in capture
    assert "evaluate_start_forecast_at_duration(start_context, validation_elapsed)" in finish
    assert 'mem["session_prediction_time_aligned"] = True' in finish


def _editable_keys() -> set[str]:
    tree = ast.parse((COMP / "settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "NATIVE_OPTION_KEYS" for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call):
                value = value.args[0]
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS not found")


def test_dashboard_settings_cover_canonical_api_without_visible_duplicate_fields():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    settings_block = js[js.index("_settingsSection(name)") : js.index("_settingsRooms()")]
    dashboard_keys = re.findall(r'_settingsField\(\{[^{}]*?key:"([^"]+)"', settings_block)
    counts = Counter(dashboard_keys)
    # Electricity price is present in two mutually exclusive heating branches;
    # it is never visible twice in the same settings view.
    assert {k: v for k, v in counts.items() if v > 1} == {"electricity_price_per_kwh": 2}
    setup_data_keys = {"outdoor_weather", "outdoor_temperature", "outdoor_humidity", "pollen_entity"}
    exposed_options = (set(dashboard_keys) - setup_data_keys) | {"resident_room_profiles"}
    assert exposed_options == _editable_keys()
    assert setup_data_keys.issubset(set(dashboard_keys))
    assert '[data-settings-section]' in js
    assert '[data-setting-control]' in js
    assert '[data-settings-action]' in js
    assert 'id="settings-save-room"' in js
    assert 'getElementById("settings-save-room")' in js

def test_settings_navigation_has_icons_and_legacy_duplicate_routes_redirect():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    home_block = js[js.index("_settingsHome()") : js.index("_settingsGroupMenu(")]
    group_block = js[js.index("_settingsGroupMenu(") : js.index("_settingsSection(name)")]
    assert "mdi:" in home_block and "mdi:" in group_block
    # Every declared dashboard navigation tuple carries an MDI icon.
    home_rows = re.findall(r'\["[^"]+","(mdi:[^"]+)","[^"]+"', home_block)
    group_rows = re.findall(r'\["[^"]+","(mdi:[^"]+)","[^"]+"\]', group_block)
    assert len(home_rows) >= 7
    assert len(group_rows) >= 10
    assert all(icon.startswith("mdi:") for icon in home_rows + group_rows)

    config = (COMP / "config_flow.py").read_text(encoding="utf-8")
    house = config[config.index("async def async_step_house"):config.index("async def async_step_personalisation")]
    personal = config[config.index("async def async_step_personalisation"):config.index("async def async_step_forecast")]
    assert "return await self.async_step_home_setup()" in house
    assert "return await self.async_step_residents()" in personal
    # Old duplicate forms remain only as compatibility schemas and are not shown
    # on a fresh/current flow.
    assert 'step_id="house"' not in house
    assert 'step_id="personalisation"' not in personal

    icons = json.loads((COMP / "icons.json").read_text(encoding="utf-8"))
    option_sections = (icons.get("options") or {}).get("step") or {}
    for step in ("add_room", "edit_room", "model", "residents"):
        assert step in option_sections


def test_frontend_no_longer_uses_systematic_same_time_basis_error_text():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "noch keine belastbare Startprognose mit gleicher Zeitbasis" not in js
    assert "aligned_prediction_accuracy_percent" not in js
    assert "prediction_accuracy_percent" in js
    assert "prediction_status_text" in js


def test_release_version_is_consistent():
    assert 'VERSION = "0.25.0.66"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))["version"] == "0.25.0.66"
    for name in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.0.66";' in (COMP / "frontend" / name).read_text(encoding="utf-8")
    assert (ROOT / "RELEASE_NOTES_0.25.0.0.md").exists()
