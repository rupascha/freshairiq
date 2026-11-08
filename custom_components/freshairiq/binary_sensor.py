"""Binary sensor platform for FreshAirIQ."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .actuator_control import automation_lock_state
from .const import CONF_AUTOMATION_LOCK_ENTITY, CONF_CONTACT_COVERS, CONF_ROOM_COVERS, CONF_ROOM_MOISTURE_SOURCES
from .entity import FreshAirIQEntity
from .room_devices import add_entities_by_room
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    house = [CrossVentilationSensor(coordinator, entry), AutomationLockSensor(coordinator, entry)]
    rooms = {
        room["key"]: [
            RoomCloseSensor(coordinator, entry, room["key"], room["name"]),
            RoomMoistureSourceSensor(coordinator, entry, room["key"], room["name"], bool(room.get(CONF_ROOM_MOISTURE_SOURCES))),
            RoomShadingSensor(coordinator, entry, room["key"], room["name"], bool(room.get(CONF_CONTACT_COVERS) or room.get(CONF_ROOM_COVERS))),
        ]
        for room in entry.data.get("rooms", [])
    }
    # 0.26.4.9: each room's entities belong to the room's sub-entry.
    add_entities_by_room(async_add_entities, entry, house, rooms)


class CrossVentilationSensor(FreshAirIQEntity, BinarySensorEntity):

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        self._attr_translation_key = "cross_ventilation"
        super().__init__(coordinator, entry, "cross_ventilation", "Cross ventilation")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["cross_ventilation"])


class AutomationLockSensor(FreshAirIQEntity, BinarySensorEntity):
    """0.26.7.0: on while the optional global automation lock is active.

    For the user's own automations (Node-RED, HA automations): FreshAirIQ itself starts no device
    action while it is on, but it cannot pause other automations – they can read this entity.
    Enabled by default only when a lock entity is configured.
    """

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        self._attr_translation_key = "automation_lock"
        super().__init__(coordinator, entry, "automation_lock", "Automation lock")
        self._attr_entity_registry_enabled_default = bool(self._lock()["configured"])

    def _lock(self) -> dict[str, Any]:
        entity = str((self._entry.options or {}).get(CONF_AUTOMATION_LOCK_ENTITY) or "").strip() or None
        state = self.hass.states.get(entity) if entity and getattr(self, "hass", None) is not None else None
        return automation_lock_state(entity, state.state if state is not None else None)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        entity = self._lock()["entity_id"]
        if entity:
            self.async_on_remove(async_track_state_change_event(self.hass, [entity], self._on_lock_change))

    @callback
    def _on_lock_change(self, _event: Event) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return bool(self._lock()["active"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lock = self._lock()
        return {**super().extra_state_attributes, "configured": lock["configured"], "lock_entity": lock["entity_id"], "lock_entity_state": lock["source_state"]}


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


_SOURCE_DETAILS = ("source", "confidence", "rate_ml_min", "generated_ml")
_NO_SOURCE = {"source": None, "confidence": 0, "rate_ml_min": None, "generated_ml": None}


class RoomMoistureSourceSensor(FreshAirIQEntity, BinarySensorEntity):
    """0.26.5.1: on while an internal moisture source (shower, bath, ...) is active.

    Enabled by default for rooms with configured moisture sources; strong
    unconfigured loads are detected too, so the entity exists for every room.
    """

    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str, configured: bool,
    ) -> None:
        self._attr_translation_key = "moisture_source"
        super().__init__(
            coordinator,
            entry,
            f"{room_key}_moisture_source",
            "Moisture source",
            room_key=room_key,
            room_name=room_name,
        )
        self.room_key = room_key
        self._attr_entity_registry_enabled_default = configured

    def _room(self) -> dict[str, Any]:
        return self.coordinator.data["rooms"].get(self.room_key, {})

    @property
    def is_on(self) -> bool:
        return bool(self._room().get("moisture_source_active"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        room = self._room()
        attributes = {
            "source": room.get("moisture_source_identified_source"),
            "confidence": int(room.get("moisture_source_confidence") or 0),
            "rate_ml_min": room.get("moisture_source_rate_ml_min"),
            "generated_ml": room.get("moisture_source_generated_ml_window"),
            "started_at": room.get("moisture_source_started_at"),
            "last_ended_at": room.get("moisture_source_last_ended_at"),
            "recovery": bool(room.get("moisture_source_recovery")),
        }
        # 0.26.5.3 (recorder load): the detector's rate and amount move with every
        # reading, also while nothing is going on. Outside an active source (or its
        # recovery) they show the values of the last source, so the entity does not
        # write a recorder row per reading.
        if room.get("moisture_source_active") or room.get("moisture_source_recovery"):
            self._last_source = {key: attributes[key] for key in _SOURCE_DETAILS}
        else:
            attributes.update(getattr(self, "_last_source", None) or dict(_NO_SOURCE))
        return attributes


class RoomShadingSensor(FreshAirIQEntity, BinarySensorEntity):
    """0.26.5.1: on while covers of the room should be closed against the sun.

    Only in the "summer cooling" profile. ``covers_to_close`` lists the covers
    whose opening gets direct sun (or, without orientation, every cover while
    the room is warm and bright). A cover leaves the list once the sun has left
    its opening; the blueprint opens it again then.
    """

    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str, configured: bool,
    ) -> None:
        self._attr_translation_key = "shading"
        super().__init__(
            coordinator,
            entry,
            f"{room_key}_shading",
            "Sun protection",
            room_key=room_key,
            room_name=room_name,
        )
        self.room_key = room_key
        self._attr_entity_registry_enabled_default = configured

    def _shading(self) -> dict[str, Any]:
        return self.coordinator.data["rooms"].get(self.room_key, {}).get("shading") or {}

    @property
    def is_on(self) -> bool:
        return bool(self._shading().get("covers_to_close"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        shading = self._shading()
        return {
            "covers_to_close": list(shading.get("covers_to_close") or []),
            "sunlit_covers": list(shading.get("sunlit_covers") or []),
            "sun_soon_covers": list(shading.get("sun_soon_covers") or []),
            "shaded_side_covers": list(shading.get("shaded_side_covers") or []),
            "sun_tracking": bool(shading.get("sun_tracking")),
        }
