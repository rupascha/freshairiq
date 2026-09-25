"""Regression contracts for v0.25.0.72 Android touch/settings-contract hardening."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def _contract_keys() -> set[str]:
    tree = ast.parse((COMP / "settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "NATIVE_OPTION_KEYS"
            for target in node.targets
        ):
            value = node.value.args[0] if isinstance(node.value, ast.Call) else node.value
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS not found")


def test_every_native_config_flow_option_field_is_bound_to_the_executable_contract():
    expected = _contract_keys()
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    bound = set(re.findall(r'native_option_key\(["\']([^"\']+)["\']\)', flow))
    assert bound == expected
    assert "from .settings_contract import native_option_key" in flow


def test_contract_accessor_fails_fast_for_unknown_option_keys():
    path = COMP / "settings_contract.py"
    spec = importlib.util.spec_from_file_location("freshairiq_settings_contract_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.native_option_key("start_rh") == "start_rh"
    try:
        module.native_option_key("definitely_not_a_freshairiq_option")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown option key must fail fast")


def test_android_webview_has_trusted_touch_swipe_regression_not_only_mouse_wheel():
    spec = (ROOT / "frontend_tests/freshairiq.spec.mjs").read_text(encoding="utf-8")
    assert "Android WebView detail overlay responds to a trusted touch swipe" in spec
    assert "newCDPSession(page)" in spec
    assert "Input.dispatchTouchEvent" in spec
    assert "type: 'touchStart'" in spec
    assert "type: 'touchMove'" in spec
    assert "type: 'touchEnd'" in spec
    assert "expect(touched).toBeGreaterThan(100)" in spec
    assert "expect(restored).toBeGreaterThan(100)" in spec


def test_version_and_release_artifact_suffix_are_consistent():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.25.0.72"
    assert policy["version"] == "0.25.0.72"
    assert package["version"] == "0.25.0.72"
    assert str(policy["release"]["artifact_suffix"]).strip()
