"""Import FreshAirIQ against the Home Assistant version installed in this job."""
from __future__ import annotations

import importlib

MODULES = [
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


def main() -> int:
    for name in MODULES:
        importlib.import_module(name)
        print(f"PASS import {name}")

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
    print("PASS Home Assistant class contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
