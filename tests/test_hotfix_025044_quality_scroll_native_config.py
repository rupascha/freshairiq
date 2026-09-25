"""Regression contract for v0.25.0.48 quality/scroll/native-config hotfix."""
from __future__ import annotations

import ast
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


def _native_option_keys() -> set[str]:
    tree = ast.parse((COMP / "settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "NATIVE_OPTION_KEYS" for target in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Call):
            value = value.args[0]
        return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS not found")


def _assert_flow_descriptions_complete(payload: dict) -> None:
    for root_name in ("config", "options"):
        steps = payload[root_name]["step"]
        for step_name, step in steps.items():
            data = step.get("data") or {}
            descriptions = step.get("data_description") or {}
            missing = set(data) - set(descriptions)
            assert not missing, f"{root_name}.{step_name} missing data_description: {sorted(missing)}"


def test_monitor_only_quality_fix_is_explicit_and_preserves_visibility_contract():
    text = (COMP / "diagnostics.py").read_text(encoding="utf-8")
    assert 'room.get("calculation_enabled") is False' in text
    assert 'room.get("monitor_only") is True' in text
    assert 'room.get("data_quality") == "monitor_only"' in text
    assert '"rooms_all_total": len(all_rooms)' in text
    assert '"rooms_monitor_only": len(monitor_only)' in text


def test_nested_detail_window_allows_native_touch_scrolling():
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    submodal_start = card.index(".submodal{")
    subdialog_start = card.index(".subdialog{", submodal_start)
    subdialog_end = card.index("}.subdialog .info-panel", subdialog_start)
    submodal_css = card[submodal_start:subdialog_start]
    subdialog_css = card[subdialog_start:subdialog_end]

    # An ancestor touch-action:none prevents descendants from re-enabling pan.
    assert "touch-action:none" not in submodal_css
    assert "touch-action:" not in submodal_css
    assert "overflow-y:auto" in subdialog_css
    assert "overflow-x:hidden" in subdialog_css
    assert "-webkit-overflow-scrolling:touch" in subdialog_css
    assert "overscroll-behavior-y:contain" in subdialog_css


def test_dashboard_and_native_options_share_one_canonical_key_contract():
    native_keys = _native_option_keys()
    assert len(native_keys) >= 90

    api = (COMP / "settings_api.py").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "EDITABLE_OPTION_KEYS = set(NATIVE_OPTION_KEYS)" in api
    assert '"settings_contract": {' in api
    for key in native_keys:
        assert f'key:"{key}"' in card, f"Dashboard missing native option: {key}"

    # The four ConfigEntry data fields are also available from the dashboard.
    for key in ("outdoor_weather", "outdoor_temperature", "outdoor_humidity", "pollen_entity"):
        assert f'key:"{key}"' in card


def test_native_flow_is_fully_documented_and_locale_specific():
    strings = json.loads((COMP / "strings.json").read_text(encoding="utf-8"))
    de = json.loads((COMP / "translations" / "de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations" / "en.json").read_text(encoding="utf-8"))

    _assert_flow_descriptions_complete(strings)
    _assert_flow_descriptions_complete(de)
    _assert_flow_descriptions_complete(en)

    # Home Assistant source/fallback strings are English; German remains a real
    # locale translation instead of being forced onto English HA profiles.
    for section in ("config", "options", "selector", "config_subentries"):
        assert strings[section] == en[section]
    assert en["config"] != de["config"]
    assert "Default:" in json.dumps(en["config"], ensure_ascii=False)
    assert "Standard:" in json.dumps(de["config"], ensure_ascii=False)
    assert "Beispiel" in json.dumps(de["options"], ensure_ascii=False)

def test_options_flow_rebases_from_current_config_entry_and_dashboard_force_reloads():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    api = (COMP / "settings_api.py").read_text(encoding="utf-8")

    assert "_normalise_legacy_entry_data(dict(self.config_entry.data))" in flow
    assert "{**DEFAULT_OPTIONS, **dict(self.config_entry.options)}" in flow
    assert "await this._loadSettings(true);" in card
    assert "async_update_entry(entry, options=options)" in api
    assert "async_update_entry(entry, data=data)" in api
