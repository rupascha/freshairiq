"""Button platform for FreshAirIQ."""
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN
from .entity import FreshAirIQEntity
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry

async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    async_add_entities([ResetLearningButton(coordinator,entry), ResetStatisticsButton(coordinator,entry)])

class ResetLearningButton(FreshAirIQEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key="reset_learning"
    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "reset_learning", "Reset learning")
    async def async_press(self) -> None:
        try:
            await self.coordinator.store.async_reset_learning()
            await self.coordinator.async_request_refresh()
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reset_learning_failed",
            ) from err

class ResetStatisticsButton(FreshAirIQEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key="reset_statistics"
    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "reset_statistics", "Reset statistics")
    async def async_press(self) -> None:
        try:
            await self.coordinator.store.async_reset_statistics()
            await self.coordinator.async_request_refresh()
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reset_statistics_failed",
            ) from err
