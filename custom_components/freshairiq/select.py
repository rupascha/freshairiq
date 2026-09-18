"""Operating profile selector for FreshAirIQ."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, PROFILE_COMFORT, PROFILE_DEHUMIDIFY, PROFILE_SUMMER_COOLING
from .entity import FreshAirIQEntity
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    async_add_entities([FreshAirIQOperatingProfileSelect(coordinator, entry)])


class FreshAirIQOperatingProfileSelect(FreshAirIQEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Betriebsmodus"
    _attr_translation_key = "operating_profile"
    _attr_options = [PROFILE_DEHUMIDIFY, PROFILE_COMFORT, PROFILE_SUMMER_COOLING]

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "operating_profile", "Betriebsmodus")

    @property
    def current_option(self) -> str:
        return str(self.coordinator.options.get("operating_profile", PROFILE_COMFORT))

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_operating_profile",
                translation_placeholders={"option": str(option)},
            )
        options = dict(self._entry.options)
        options["operating_profile"] = option
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        # Mirror the selected option immediately; the expensive house-wide
        # recalculation follows asynchronously and no longer blocks the service
        # call used by the dashboard.
        self.async_write_ha_state()
        self.hass.async_create_task(self.coordinator.async_request_refresh())
