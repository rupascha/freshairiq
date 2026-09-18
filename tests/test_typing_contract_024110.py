"""Static contract checks for the typed Home Assistant surface in v0.25.0.7."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "freshairiq"

_TYPED_SURFACE = (
    "__init__.py",
    "runtime.py",
    "entity.py",
    "binary_sensor.py",
    "button.py",
    "number.py",
    "select.py",
    "sensor.py",
    "repairs.py",
    "coordinator.py",
    "settings_api.py",
)


def _untyped_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if any(arg.annotation is None for arg in args if arg.arg not in {"self", "cls"}):
            missing.append(node.name)
            continue
        if node.returns is None:
            missing.append(node.name)
    return missing


def test_typed_runtime_surface_has_no_unannotated_function_signatures() -> None:
    failures = {
        name: _untyped_functions(PKG / name)
        for name in _TYPED_SURFACE
        if _untyped_functions(PKG / name)
    }
    assert failures == {}


def test_runtime_data_is_the_only_per_entry_runtime_store() -> None:
    runtime = (PKG / "runtime.py").read_text(encoding="utf-8")
    config_flow = (PKG / "config_flow.py").read_text(encoding="utf-8")
    settings = (PKG / "settings_api.py").read_text(encoding="utf-8")

    assert "entry.runtime_data = coordinator" in runtime
    assert "hass.data.setdefault(DOMAIN" not in runtime
    assert "hass.data.get(DOMAIN" not in config_flow
    assert "hass.data.get(DOMAIN" not in settings


def test_distribution_exposes_typing_marker_and_config_entry_alias() -> None:
    assert (PKG / "py.typed").is_file()
    typing_source = (PKG / "typing.py").read_text(encoding="utf-8")
    assert "FreshAirIQConfigEntry" in typing_source
    assert "ConfigEntry[FreshAirIQCoordinator | None]" in typing_source
