"""Binary sensor platform for FreshAirIQ."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FreshAirIQEntity
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    entities = [CrossVentilationSensor(coordinator, entry)]
    for room in entry.data.get("rooms", []):
        entities.append(RoomCloseSensor(coordinator, entry, room["key"], room["name"]))
    async_add_entities(entities)


class CrossVentilationSensor(FreshAirIQEntity, BinarySensorEntity):

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "cross_ventilation", "Cross ventilation")
        self._attr_translation_key = "cross_ventilation"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["cross_ventilation"])


class RoomCloseSensor(FreshAirIQEntity, BinarySensorEntity):

    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            f"{room_key}_close_recommended",
            "Close recommended",
            room_key=room_key,
            room_name=room_name,
        )
        self.room_key = room_key
        self._attr_translation_key = "close_recommended"

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data["rooms"].get(self.room_key, {}).get("close_recommended")
        )
