"""Shared Home Assistant type aliases for FreshAirIQ."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import FreshAirIQCoordinator

    FreshAirIQConfigEntry: TypeAlias = ConfigEntry[FreshAirIQCoordinator | None]
else:
    # Runtime users only need the name to exist because annotations are
    # postponed. Keeping Home Assistant imports under TYPE_CHECKING preserves
    # the standalone pure-logic test environment without weakening static types.
    FreshAirIQConfigEntry = Any
