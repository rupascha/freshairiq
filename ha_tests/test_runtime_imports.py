"""Home Assistant runtime smoke tests.

This suite deliberately lives outside tests/ so tests/conftest.py cannot replace
Home Assistant with namespace stubs. It must be executed only in CI/jobs where
Home Assistant itself is installed.
"""
from __future__ import annotations

import importlib

import pytest


RUNTIME_MODULES = [
    "custom_components.freshairiq",
    "custom_components.freshairiq.config_flow",
    "custom_components.freshairiq.coordinator",
    "custom_components.freshairiq.sensor",
    "custom_components.freshairiq.diagnostics",
    "custom_components.freshairiq.settings_api",
    "custom_components.freshairiq.storage",
    "custom_components.freshairiq.typing",
    "custom_components.freshairiq.entity",
    "custom_components.freshairiq.binary_sensor",
    "custom_components.freshairiq.button",
    "custom_components.freshairiq.number",
    "custom_components.freshairiq.select",
]


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_module_imports_against_supported_home_assistant(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


def test_config_flow_and_coordinator_classes_are_registered() -> None:
    from homeassistant import config_entries
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from custom_components.freshairiq.config_flow import (
        FreshAirIQConfigFlow,
        FreshAirIQOptionsFlow,
        FreshAirIQRoomSubentryFlow,
    )
    from custom_components.freshairiq.coordinator import FreshAirIQCoordinator

    assert issubclass(FreshAirIQConfigFlow, config_entries.ConfigFlow)
    assert issubclass(FreshAirIQOptionsFlow, config_entries.OptionsFlow)
    assert issubclass(FreshAirIQRoomSubentryFlow, config_entries.ConfigSubentryFlow)
    assert issubclass(FreshAirIQCoordinator, DataUpdateCoordinator)
