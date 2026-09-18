"""User-adjustable FreshAirIQ numeric controls."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FreshAirIQEntity
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    async_add_entities([
        FreshAirIQForecastHorizonNumber(coordinator, entry),
        FreshAirIQGuestAdultsNumber(coordinator, entry),
        FreshAirIQGuestChildrenNumber(coordinator, entry),
    ])


class _FreshAirIQOptionNumber(FreshAirIQEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    option_key: str

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator, entry, key, name)
        self.option_key = key

    @property
    def native_value(self) -> float:
        return float(self.coordinator.options.get(self.option_key, 0))

    async def _set_option(self, value: float) -> None:
        options = dict(self._entry.options)
        options[self.option_key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        # The option value itself is authoritative immediately. Publish the new
        # number state now so dashboard controls react without waiting for the
        # complete forecast/decision pipeline, then recompute in the background.
        self.async_write_ha_state()
        self.hass.async_create_task(self.coordinator.async_request_refresh())


class FreshAirIQForecastHorizonNumber(_FreshAirIQOptionNumber):
    _attr_translation_key = "forecast_horizon"
    _attr_native_min_value = 1
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "forecast_horizon_min", "Prognosezeitraum")
        self._attr_unique_id = f"{entry.entry_id}_forecast_horizon"

    async def async_set_native_value(self, value: float) -> None:
        await self._set_option(int(round(min(max(float(value), 1.0), 120.0))))


class FreshAirIQGuestAdultsNumber(_FreshAirIQOptionNumber):
    _attr_translation_key = "guest_adults"
    _attr_native_min_value = 0
    _attr_native_max_value = 20
    _attr_native_step = 1

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "guest_adults", "Übernachtungsgäste Erwachsene")
        self._attr_unique_id = f"{entry.entry_id}_guest_adults"

    async def async_set_native_value(self, value: float) -> None:
        await self._set_option(int(round(min(max(float(value), 0.0), 20.0))))


class FreshAirIQGuestChildrenNumber(_FreshAirIQOptionNumber):
    _attr_translation_key = "guest_children"
    _attr_native_min_value = 0
    _attr_native_max_value = 20
    _attr_native_step = 1

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry) -> None:
        super().__init__(coordinator, entry, "guest_children", "Übernachtungsgäste Kinder")
        self._attr_unique_id = f"{entry.entry_id}_guest_children"

    async def async_set_native_value(self, value: float) -> None:
        await self._set_option(int(round(min(max(float(value), 0.0), 20.0))))
