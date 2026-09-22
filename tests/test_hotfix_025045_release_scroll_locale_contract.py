"""Regression contracts for v0.25.0.48 release/scroll/locale hardening."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _native_option_keys() -> set[str]:
    tree = ast.parse((COMP / "settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "NATIVE_OPTION_KEYS"
            for target in node.targets
        ):
            value = node.value.args[0] if isinstance(node.value, ast.Call) else node.value
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS not found")


def test_release_waits_for_full_reusable_quality_workflow():
    quality = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "workflow_call:" in quality
    assert "uses: ./.github/workflows/quality.yml" in release
    assert "needs: quality" in release
    assert "needs: verify-release" in release
    assert "gh release create" in release


def test_stability_runtime_is_advisory_while_dedicated_performance_gate_remains_hard():
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    stability = (ROOT / "tools/stability_gate.py").read_text(encoding="utf-8")
    quality = (ROOT / "tools/quality_gate.py").read_text(encoding="utf-8")
    assert policy["stability"]["runtime_enforcement"] == "advisory"
    assert 'runtime_enforcement == "hard"' in stability
    assert "performance_gate.py" in stability
    assert '"performance regression"' in quality


def test_native_and_dashboard_settings_are_contract_checked_on_both_surfaces():
    keys = _native_option_keys()
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    card = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")
    for key in keys:
        assert f'"{key}"' in flow or f"'{key}'" in flow, f"Native flow missing {key}"
        assert f'key:"{key}"' in card, f"Dashboard missing {key}"


def test_config_flow_labels_match_real_defaults_and_ranges():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    assert de["config"]["step"]["more_rooms"]["data"]["add_another"].endswith("Standard: an)")
    assert en["config"]["step"]["more_rooms"]["data"]["add_another"].endswith("default: on)")
    assert "1 und 365" in de["options"]["step"]["data_learning_settings"]["menu_option_descriptions"]["statistics"]
    assert "1 and 365" in en["options"]["step"]["data_learning_settings"]["menu_option_descriptions"]["statistics"]


def test_locales_are_not_forced_to_german_anymore():
    strings = json.loads((COMP / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    assert strings["config"] == en["config"]
    assert strings["options"] == en["options"]
    assert en["config"] != de["config"]
