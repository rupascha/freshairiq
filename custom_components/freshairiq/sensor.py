"""Sensor platform for FreshAirIQ."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSION
from .entity import FreshAirIQEntity
from .runtime import get_runtime_coordinator
from .coordinator import FreshAirIQCoordinator
from .typing import FreshAirIQConfigEntry


@dataclass(frozen=True)
class Description:
    key: str
    name: str
    value: Callable[[dict[str, Any]], object]
    unit: str | None = None
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    enabled_default: bool = True


HOUSE = (
    Description("status", "Status", lambda d: d["status"], icon="mdi:home-air-filter"),
    Description("potential_total_ml", "Removable moisture", lambda d: d["potential_total_ml"], "mL", "mdi:water-minus"),
    Description("live_balance_ml", "Live moisture balance", lambda d: d["live_balance_ml"], "mL", "mdi:water-sync"),
    Description("next_5_min_ml", "Next 5 minutes", lambda d: d["next_5_min_ml"], "mL", "mdi:water-clock-outline"),
    Description("forecast_moisture_effect_ml", "Forecast moisture effect", lambda d: d.get("forecast_moisture_effect_ml", 0), "mL", "mdi:chart-timeline-variant-shimmer"),
    Description("forecast_temperature_change_c", "Forecast temperature change", lambda d: d.get("forecast_temperature_change_c", 0), "°C", device_class=SensorDeviceClass.TEMPERATURE_DELTA),
    Description("forecast_cost", "Forecast reheating cost", lambda d: d.get("forecast_cost", 0), "€", "mdi:currency-eur"),
    Description("forecast_confidence", "Forecast confidence", lambda d: d.get("forecast_confidence", 0), PERCENTAGE, "mdi:shield-check-outline"),
    Description("max_surface_rh", "Highest estimated surface humidity", lambda d: d["max_surface_rh"], PERCENTAGE, device_class=SensorDeviceClass.HUMIDITY),
    Description("total_water_ml", "Water vapor in monitored air", lambda d: d["total_water_ml"], "mL", "mdi:water-outline"),
    Description("prognosis_confidence", "Learning confidence", lambda d: d["prognosis_confidence"], PERCENTAGE, "mdi:shield-check-outline"),
    Description("recommended_duration_min", "Recommended ventilation duration", lambda d: d["recommended_duration_min"], "min", device_class=SensorDeviceClass.DURATION),
    Description("remaining_duration_min", "Ventilation time remaining", lambda d: d["remaining_duration_min"], "min", device_class=SensorDeviceClass.DURATION),
    Description("temperature_change_live_c", "Temperature change since ventilation start", lambda d: d["temperature_change_live_c"], "°C", device_class=SensorDeviceClass.TEMPERATURE_DELTA),
    Description("overnight_forecast_ml", "Overnight moisture forecast", lambda d: d["overnight_forecast_ml"], "mL", "mdi:weather-night"),
    Description("overnight_confidence", "Overnight forecast confidence", lambda d: d.get("overnight_confidence", 0), PERCENTAGE, "mdi:shield-moon-outline"),
    Description("effective_occupants", "Expected people at home", lambda d: d.get("effective_occupants", 0), None, "mdi:account-group"),
    Description("night_model_ml_h", "Learned night moisture rate", lambda d: d["night_model_ml_h"], "mL/h", "mdi:chart-timeline-variant"),
    Description("history_removed_14d_ml", "Removed moisture selected period", lambda d: d["history_summary"]["removed_ml"], "mL", "mdi:water-minus"),
    Description("history_cost_14d", "Estimated ventilation cost selected period", lambda d: d["history_summary"]["cost"], "€", "mdi:currency-eur"),
    Description("estimated_moisture_generation_day_ml", "Estimated daily moisture generation", lambda d: d["estimated_moisture_generation_day_ml"], "mL", "mdi:water-plus"),
    Description("moisture_balance_today_ml", "Estimated moisture balance today", lambda d: d["moisture_balance_today_ml"], "mL", "mdi:scale-balance"),
    Description("last_learning_diagnosis", "Last learning diagnosis", lambda d: d["last_learning_diagnosis"], icon="mdi:brain", enabled_default=False),
)

ROOM_FIELDS = (
    ("action", "Action", None, "mdi:weather-windy", None, True),
    ("absolute_humidity", "Absolute humidity", "g/m³", None, SensorDeviceClass.ABSOLUTE_HUMIDITY, True),
    ("delta_g_m3", "Humidity difference", "g/m³", "mdi:delta", None, True),
    ("potential_ml", "Moisture potential", "mL", "mdi:water-minus", None, True),
    ("next_5_min_ml", "Next 5 minutes", "mL", "mdi:water-clock-outline", None, True),
    ("temp_next_5_min_c", "Temperature next 5 minutes", "°C", None, SensorDeviceClass.TEMPERATURE, True),
    ("surface_rh", "Estimated surface humidity", PERCENTAGE, None, SensorDeviceClass.HUMIDITY, True),
    ("mould_level", "Mould risk", None, "mdi:alert-outline", None, True),
    ("learning_status", "Learning status", None, "mdi:brain", None, True),
    ("learning_samples", "Learning samples", None, "mdi:counter", None, False),
    ("result_ml", "Session moisture balance", "mL", "mdi:water-sync", None, True),
    ("learning_diagnosis", "Learning diagnosis", None, "mdi:brain", None, False),
    ("session_elapsed_min", "Ventilation session elapsed", "min", None, SensorDeviceClass.DURATION, True),
    ("temperature_change_c", "Temperature change since session start", "°C", None, SensorDeviceClass.TEMPERATURE_DELTA, True),
    ("next_5_min_cost", "Estimated cost next 5 minutes", "€", "mdi:currency-eur", None, True),
    ("moisture_effect_next_5_min_ml", "Moisture effect next 5 minutes", "mL", "mdi:water-sync", None, True),
    ("forecast_moisture_effect_ml", "Forecast moisture effect", "mL", "mdi:chart-timeline-variant-shimmer", None, True),
    ("forecast_temperature_change_c", "Forecast temperature change", "°C", None, SensorDeviceClass.TEMPERATURE_DELTA, True),
    ("forecast_cost", "Forecast reheating cost", "€", "mdi:currency-eur", None, True),
    ("forecast_confidence", "Forecast confidence", PERCENTAGE, "mdi:shield-check-outline", None, True),
)


ACTION_STATE_MAP = {
    "Check sensor": "check_sensor",
    "Close": "close",
    "Continue ventilating": "continue_ventilating",
    "Ventilate": "ventilate",
    "Do not ventilate": "do_not_ventilate",
    "Wait": "wait",
    "Okay": "okay",
    "Ventilate for cooling": "ventilate_for_cooling",
    "Monitor only": "monitor_only",
}

MOULD_STATE_MAP = {
    "Unknown": "unknown",
    "Very high": "very_high",
    "High": "high",
    "Elevated": "elevated",
    "Slightly elevated": "slightly_elevated",
    "Low": "low",
}

LEARNING_STATE_MAP = {
    "Very stable": "very_stable",
    "Stable": "stable",
    "Usable": "usable",
    "Learning": "learning",
    "Base estimate": "base_estimate",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    entities = [HouseSensor(coordinator, entry, desc) for desc in HOUSE]
    for room in entry.data.get("rooms", []):
        for field, label, unit, icon, device_class, enabled_default in ROOM_FIELDS:
            entities.append(
                RoomSensor(
                    coordinator,
                    entry,
                    room["key"],
                    room["name"],
                    field,
                    label,
                    unit,
                    icon,
                    device_class,
                    enabled_default,
                )
            )
    async_add_entities(entities)


class HouseSensor(FreshAirIQEntity, SensorEntity):
    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry, desc: Description) -> None:
        super().__init__(coordinator, entry, desc.key, desc.name)
        self.desc = desc
        self._attr_translation_key = desc.key
        self._attr_native_unit_of_measurement = desc.unit
        self._attr_device_class = desc.device_class
        self._attr_entity_registry_enabled_default = desc.enabled_default

    @property
    def native_value(self) -> object:
        return self.desc.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.desc.key == "status":
            return {
                "status": self.coordinator.data.get("status"),
                "status_text": self.coordinator.data["status_text"],
                # Hotfix 0.18.2.3: keep the complete room payload as the authoritative
                # fallback. Per-room Action entities still expose the same payload, but
                # disabling/missing one of those entities must never remove room history
                # from the dashboard.
                "rooms": self.coordinator.data["rooms"],
                "freshairiq_transport": "status_v2",
                "freshairiq_entry_id": self._entry.entry_id,
                "freshairiq_version": VERSION,
                "levels": self.coordinator.data.get("levels", []),
                "potential_total_ml": self.coordinator.data.get("potential_total_ml", 0),
                "live_balance_ml": self.coordinator.data.get("live_balance_ml", 0),
                "next_5_min_ml": self.coordinator.data.get("next_5_min_ml", 0),
                "next_5_min_effect_ml": self.coordinator.data.get("next_5_min_effect_ml", 0),
                "moisture_gain_next_5_min_ml": self.coordinator.data.get("moisture_gain_next_5_min_ml", 0),
                "forecast_horizon_min": self.coordinator.data.get("forecast_horizon_min", 5),
                "forecast_moisture_effect_ml": self.coordinator.data.get("forecast_moisture_effect_ml", 0),
                "forecast_uncapped_moisture_effect_ml": self.coordinator.data.get("forecast_uncapped_moisture_effect_ml", self.coordinator.data.get("forecast_moisture_effect_ml", 0)),
                "forecast_target_limited": self.coordinator.data.get("forecast_target_limited", False),
                "forecast_live_adapted": self.coordinator.data.get("forecast_live_adapted", False),
                "forecast_live_observation_weight": self.coordinator.data.get("forecast_live_observation_weight", 0),
                "forecast_temperature_change_c": self.coordinator.data.get("forecast_temperature_change_c", 0),
                "forecast_cost": self.coordinator.data.get("forecast_cost", 0),
                "forecast_heat_kwh": self.coordinator.data.get("forecast_heat_kwh", 0),
                "forecast_confidence": self.coordinator.data.get("forecast_confidence", 0),
                "total_water_ml": self.coordinator.data.get("total_water_ml", 0),
                "max_surface_rh": self.coordinator.data.get("max_surface_rh", 0),
                "prognosis_confidence": self.coordinator.data.get("prognosis_confidence", 0),
                "cross_ventilation": self.coordinator.data["cross_ventilation"],
                "recommended_duration_min": self.coordinator.data["recommended_duration_min"],
                "remaining_duration_min": self.coordinator.data["remaining_duration_min"],
                "temperature_change_live_c": self.coordinator.data["temperature_change_live_c"],
                "operating_profile": self.coordinator.data["operating_profile"],
                "overnight_forecast_ml": self.coordinator.data["overnight_forecast_ml"],
                "overnight_forecast_base_ml": self.coordinator.data.get("overnight_forecast_base_ml", 0),
                "overnight_weather_effect_ml": self.coordinator.data.get("overnight_weather_effect_ml", 0),
                "overnight_trend_effect_ml": self.coordinator.data.get("overnight_trend_effect_ml", 0),
                "overnight_hours_remaining": self.coordinator.data.get("overnight_hours_remaining", 0),
                "overnight_confidence": self.coordinator.data.get("overnight_confidence", 0),
                "night_model_ml_h": self.coordinator.data["night_model_ml_h"],
                "night_model_samples": self.coordinator.data["night_model_samples"],
                "night_recommendation": self.coordinator.data["night_recommendation"],
                "night_strategy": self.coordinator.data.get("night_strategy", {}),
                "history_14d": self.coordinator.data["history_14d"],
                "water_history_14d": self.coordinator.data.get("water_history_14d", []),
                "temperature_history_14d": self.coordinator.data.get("temperature_history_14d", []),
                "history_summary": self.coordinator.data["history_summary"],
                "occupants": self.coordinator.data["occupants"],
                "heating_system": self.coordinator.data["heating_system"],
                "energy_price_per_kwh": self.coordinator.data.get("energy_price_per_kwh", 0),
                "adult_occupants": self.coordinator.data.get("adult_occupants", 0),
                "child_occupants": self.coordinator.data.get("child_occupants", 0),
                "effective_occupants": self.coordinator.data.get("effective_occupants", 0),
                "effective_adults": self.coordinator.data.get("effective_adults", 0),
                "effective_children": self.coordinator.data.get("effective_children", 0),
                "tracked_occupants": self.coordinator.data.get("tracked_occupants", 0),
                "home_tracked_occupants": self.coordinator.data.get("home_tracked_occupants", 0),
                "away_tracked_occupants": self.coordinator.data.get("away_tracked_occupants", 0),
                "unknown_tracked_occupants": self.coordinator.data.get("unknown_tracked_occupants", 0),
                "untracked_adults": self.coordinator.data.get("untracked_adults", 0),
                "untracked_children": self.coordinator.data.get("untracked_children", 0),
                "guest_adults": self.coordinator.data.get("guest_adults", 0),
                "guest_children": self.coordinator.data.get("guest_children", 0),
                "presence_confidence": self.coordinator.data.get("presence_confidence", 0),
                "property_type": self.coordinator.data.get("property_type", "house"),
                "ventilation_threshold_ml": self.coordinator.data.get("ventilation_threshold_ml", 0),
                "ventilation_threshold_percent": self.coordinator.data.get("ventilation_threshold_percent", 10),
                "ventilation_threshold_mode": self.coordinator.data.get("ventilation_threshold_mode", "adaptive_home_size"),
                "presence_explanation": self.coordinator.data.get("presence_explanation", ""),
                "pets_in_household": self.coordinator.data.get("pets_in_household", False),
                "house_strategy_samples": self.coordinator.data.get("house_strategy_samples", 0),
                "pollen_enabled": self.coordinator.data.get("pollen_enabled", False),
                "pollen_index": self.coordinator.data.get("pollen_index", 0),
                "pollen_limit": self.coordinator.data.get("pollen_limit", 4),
                "pollen_blocked": self.coordinator.data.get("pollen_blocked", False),
                "wind_bearing": self.coordinator.data.get("wind_bearing"),
                "wind_speed": self.coordinator.data.get("wind_speed"),
                "last_ventilation": self.coordinator.data.get("last_ventilation"),
                "finalizing_measurements": self.coordinator.data.get("finalizing_measurements", {}),
                "statistics_days": self.coordinator.data.get("statistics_days", 14),
                "notifications_enabled": self.coordinator.data["notifications_enabled"],
                "intelligent_recommendation": self.coordinator.data.get("intelligent_recommendation", {}),
                "recommendation_engine": self.coordinator.data.get("recommendation_engine", "v3"),
                "iq_state": self.coordinator.data.get("iq_state", {}),
                "future_weather_available": self.coordinator.data.get("future_weather_available", False),
                "intelligence_engine": self.coordinator.data.get("intelligence_engine", "v1"),
                "estimated_moisture_generation_day_ml": self.coordinator.data["estimated_moisture_generation_day_ml"],
                "moisture_balance_today_ml": self.coordinator.data["moisture_balance_today_ml"],
                "forecast_validation": self.coordinator.data.get("forecast_validation", {}),
                "forecast_backtest": self.coordinator.data.get("forecast_backtest", {}),
                "post_close_stabilization": self.coordinator.data.get("post_close_stabilization", {}),
                "learning_components": self.coordinator.data.get("learning_components", {}),
                "diagnostics": self.coordinator.data.get("diagnostics", {}),
                "version": VERSION,
            }
        return None


class RoomSensor(FreshAirIQEntity, SensorEntity):
    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str, field: str, label: str, unit: str | None,
        icon: str | None, device_class: SensorDeviceClass | None = None,
        enabled_default: bool = True,
    ) -> None:
        # Entity name is only the measurement; the device supplies the room name.
        super().__init__(
            coordinator,
            entry,
            f"{room_key}_{field}",
            label,
            room_key=room_key,
            room_name=room_name,
        )
        self.room_key = room_key
        self.field = field
        self._attr_translation_key = field
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> object:
        value = self.coordinator.data["rooms"].get(self.room_key, {}).get(self.field)
        if self.field == "action":
            return ACTION_STATE_MAP.get(value, "unknown")
        if self.field == "mould_level":
            return MOULD_STATE_MAP.get(value, "unknown")
        if self.field == "learning_status":
            return LEARNING_STATE_MAP.get(value, "base_estimate")
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        # Robust dashboard transport: expose the complete room payload on exactly
        # one entity per room. This avoids relying exclusively on the central
        # status entity, which may be disabled/renamed or shadowed by an older
        # registry entity after upgrades. No calculation logic is changed.
        if self.field == "action":
            room = self.coordinator.data.get("rooms", {}).get(self.room_key)
            if room:
                return {
                    "freshairiq_room_payload": room,
                    "freshairiq_room_key": self.room_key,
                    "freshairiq_transport": "room_v2",
                    "freshairiq_entry_id": self._entry.entry_id,
                    "freshairiq_version": VERSION,
                }
        return None

    @property
    def available(self) -> bool:
        room = self.coordinator.data.get("rooms", {}).get(self.room_key)
        return super().available and bool(room) and room.get("data_quality") == "ok"
