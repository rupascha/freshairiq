"""Binary sensor platform for FreshAirIQ."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FreshAirIQEntity
from .room_devices import add_entities_by_room
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    house = [CrossVentilationSensor(coordinator, entry)]
    rooms = {room["key"]: [RoomCloseSensor(coordinator, entry, room["key"], room["name"])] for room in entry.data.get("rooms", [])}
    # 0.26.4.9: each room's entities belong to the room's sub-entry.
    add_entities_by_room(async_add_entities, entry, house, rooms)


class CrossVentilationSensor(FreshAirIQEntity, BinarySensorEntity):

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        self._attr_translation_key = "cross_ventilation"
        super().__init__(coordinator, entry, "cross_ventilation", "Cross ventilation")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["cross_ventilation"])


class RoomCloseSensor(FreshAirIQEntity, BinarySensorEntity):

    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str
    ) -> None:
        self._attr_translation_key = "close_recommended"
        super().__init__(
            coordinator,
            entry,
            f"{room_key}_close_recommended",
            "Close recommended",
            room_key=room_key,
            room_name=room_name,
        )
        self.room_key = room_key

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data["rooms"].get(self.room_key, {}).get("close_recommended")
        )
