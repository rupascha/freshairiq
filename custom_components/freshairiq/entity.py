"""Entity base classes for FreshAirIQ."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


class FreshAirIQEntity(CoordinatorEntity):
    """Base entity with stable device registry information."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreshAirIQCoordinator,
        entry: FreshAirIQConfigEntry,
        key: str,
        name: str,
        *,
        room_key: str | None = None,
        room_name: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name

        if room_key is None:
            # Central FreshAirIQ hub device.
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
                translation_key="hub",
                manufacturer="rupascha",
                model="FreshAirIQ Core",
                model_id="V14.2.1",
                sw_version=VERSION,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}:room:{room_key}")},
                translation_key="room",
                translation_placeholders={"room_name": room_name or room_key},
                manufacturer="rupascha",
                model="FreshAirIQ RM",
                model_id="FAIQ-RM1",
                sw_version=VERSION,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Stable FreshAirIQ identity for dashboard entity resolution."""
        return {
            "freshairiq_entry_id": self._entry.entry_id,
            "freshairiq_version": VERSION,
            "freshairiq_entity_key": self._key,
        }
