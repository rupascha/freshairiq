"""Release contracts for the v0.25.0.7 optional-sensor/settings update."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "freshairiq"


def _editable_option_keys() -> set[str]:
    tree = ast.parse((PKG / "settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "NATIVE_OPTION_KEYS" for target in node.targets):
            value = node.value
            if isinstance(value, ast.Call):
                value = value.args[0]
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS not found")


def test_optional_sensor_controls_share_the_integration_settings_store() -> None:
    """VOC/PM2.5/illuminance controls must be global integration options."""
    frontend = (PKG / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    flow = (PKG / "config_flow.py").read_text(encoding="utf-8")
    editable = _editable_option_keys()

    for key in ("voc_sensor_enabled", "pm25_sensor_enabled", "illuminance_sensor_enabled"):
        assert key in editable
        assert key in flow
        assert f'["{key}",' in frontend
        assert "data-global-sensor-key" in frontend
    assert 'action:"set_option"' in frontend
    assert "OPTIONALE ZUSATZSENSOREN · GLOBAL" in frontend


def test_dashboard_and_native_editable_option_surfaces_remain_in_parity() -> None:
    """Every ordinary editable option has a dashboard field and native-flow key."""
    frontend = (PKG / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    flow = (PKG / "config_flow.py").read_text(encoding="utf-8")
    editable = _editable_option_keys()
    dashboard_fields = set(re.findall(r'_settingsField\(\{[^{}]*?key:\s*"([^"]+)"', frontend))

    # resident_room_profiles is deliberately rendered by the richer profile editor.
    assert editable - dashboard_fields == {"resident_room_profiles"}
    for key in editable:
        assert f'"{key}"' in flow or f"'{key}'" in flow


def test_optional_sensor_diagnostics_contract_is_exportable_for_30_days() -> None:
    """Beta diagnostics must retain the new optional sensor signals and state."""
    diagnostics = (PKG / "diagnostics.py").read_text(encoding="utf-8")
    assert "DIAGNOSTICS_SCHEMA_VERSION = 10" in diagnostics
    assert "DIAGNOSTICS_RETENTION_DAYS = 30" in diagnostics
    for prefix in ("voc", "pm25", "illuminance"):
        for suffix in ("", "_available", "_enabled", "_configured"):
            assert f'"{prefix}{suffix}"' in diagnostics
        assert f'"{prefix}_room_count"' in diagnostics


def test_devices_services_sections_have_icons_and_german_optional_sensor_copy() -> None:
    """Native options sections keep icons and complete German explanations."""
    icons = json.loads((PKG / "icons.json").read_text(encoding="utf-8"))
    de = json.loads((PKG / "translations" / "de.json").read_text(encoding="utf-8"))

    option_steps = icons["options"]["step"]
    for step in ("add_room", "edit_room", "model", "residents"):
        assert option_steps[step]["sections"]
        assert all(str(icon).startswith("mdi:") for icon in option_steps[step]["sections"].values())

    air = de["options"]["step"]["air_quality"]
    assert "vollständig optional" in air["description"]
    assert "ml-Prognose" in air["description"]
    assert "30-Tage-Diagnostik" in air["description"]


def test_initial_setup_no_longer_forces_room_configuration() -> None:
    """Initial setup creates the integration before any room is required."""
    flow = (PKG / "config_flow.py").read_text(encoding="utf-8")
    start = flow.index("async def async_step_user")
    end = flow.index("async def async_step_reconfigure", start)
    user_step = flow[start:end]
    assert "self._base.setdefault(CONF_ROOMS, [])" in user_step
    assert "self.async_create_entry" in user_step
    assert "async_step_room" not in user_step
