"""Typed runtime access helpers for FreshAirIQ."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .coordinator import FreshAirIQCoordinator
    from .typing import FreshAirIQConfigEntry


def set_runtime_coordinator(
    hass: "HomeAssistant",
    entry: "FreshAirIQConfigEntry",
    coordinator: "FreshAirIQCoordinator",
) -> None:
    """Store the coordinator in Home Assistant's canonical runtime_data slot."""
    del hass  # The parameter keeps the helper API stable for existing callers.
    entry.runtime_data = coordinator


def get_runtime_coordinator(
    hass: "HomeAssistant", entry: "FreshAirIQConfigEntry"
) -> "FreshAirIQCoordinator":
    """Return the loaded coordinator from ConfigEntry.runtime_data."""
    del hass
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        raise RuntimeError("FreshAirIQ ConfigEntry has no loaded runtime_data")
    return coordinator


def clear_runtime_coordinator(
    hass: "HomeAssistant", entry: "FreshAirIQConfigEntry"
) -> None:
    """Clear the runtime slot after a successful unload or failed setup."""
    del hass
    entry.runtime_data = None


def iter_runtime_coordinators(hass: "HomeAssistant") -> list["FreshAirIQCoordinator"]:
    """Return loaded FreshAirIQ coordinators from ConfigEntry.runtime_data only."""
    coordinators: list["FreshAirIQCoordinator"] = []
    seen: set[int] = set()
    config_entries = getattr(hass, "config_entries", None)
    async_entries = getattr(config_entries, "async_entries", None)
    if not callable(async_entries):
        return []
    entries = async_entries("freshairiq")
    for entry in entries:
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None or id(runtime) in seen:
            continue
        coordinators.append(runtime)
        seen.add(id(runtime))
    return coordinators
