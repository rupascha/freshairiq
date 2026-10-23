"""Sensor platform for FreshAirIQ."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import MATCH_ALL, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .dashboard_live import LIVE_API
from .dashboard_transport import DETAILS_API, hold_source_details, stable_room_payload
from .opening_strategy import HOUSE_ALIGNED_STATES
from .publish_filter import quantized, with_deadband
from .const import VERSION
from .room_devices import add_entities_by_room
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
    step: float | None = None  # 0.26.5.3: publish in steps (recorder load)
    deadband: float | None = None


HOUSE = (
    Description("status", "Status", lambda d: d["status"], icon="mdi:home-air-filter"),
    Description("potential_total_ml", "Removable moisture", lambda d: d["potential_total_ml"], "mL", "mdi:water-minus"),
    Description("live_balance_ml", "Live moisture balance", lambda d: d["live_balance_ml"], "mL", "mdi:water-sync"),
    Description("next_5_min_ml", "Next 5 minutes", lambda d: d["next_5_min_ml"], "mL", "mdi:water-clock-outline"),
    Description("forecast_moisture_effect_ml", "Forecast moisture effect", lambda d: d.get("forecast_moisture_effect_ml", 0), "mL", "mdi:chart-timeline-variant-shimmer"),
    Description("forecast_temperature_change_c", "Forecast temperature change", lambda d: d.get("forecast_temperature_change_c", 0), "°C", device_class=SensorDeviceClass.TEMPERATURE_DELTA, deadband=0.2),
    Description("forecast_cost", "Forecast reheating cost", lambda d: d.get("forecast_cost", 0), "€", "mdi:currency-eur"),
    Description("forecast_confidence", "Forecast confidence", lambda d: d.get("forecast_confidence", 0), PERCENTAGE, "mdi:shield-check-outline"),
    Description("max_surface_rh", "Highest estimated surface humidity", lambda d: d["max_surface_rh"], PERCENTAGE, device_class=SensorDeviceClass.HUMIDITY),
    Description("total_water_ml", "Water vapor in monitored air", lambda d: d["total_water_ml"], "mL", "mdi:water-outline"),
    Description("prognosis_confidence", "Learning confidence", lambda d: d["prognosis_confidence"], PERCENTAGE, "mdi:shield-check-outline"),
    Description("recommended_duration_min", "Recommended ventilation duration", lambda d: d["recommended_duration_min"], "min", device_class=SensorDeviceClass.DURATION),
    Description("remaining_duration_min", "Ventilation time remaining", lambda d: d["remaining_duration_min"], "min", device_class=SensorDeviceClass.DURATION),
    Description("temperature_change_live_c", "Temperature change since ventilation start", lambda d: d["temperature_change_live_c"], "°C", device_class=SensorDeviceClass.TEMPERATURE_DELTA),
    Description("overnight_forecast_ml", "Overnight moisture forecast", lambda d: d["overnight_forecast_ml"], "mL", "mdi:weather-night", step=50),
    Description("overnight_confidence", "Overnight forecast confidence", lambda d: d.get("overnight_confidence", 0), PERCENTAGE, "mdi:shield-moon-outline"),
    Description("effective_occupants", "Expected people at home", lambda d: d.get("effective_occupants", 0), None, "mdi:account-group"),
    Description("night_model_ml_h", "Learned night moisture rate", lambda d: d["night_model_ml_h"], "mL/h", "mdi:chart-timeline-variant"),
    Description("history_removed_14d_ml", "Removed moisture selected period", lambda d: d["history_summary"]["removed_ml"], "mL", "mdi:water-minus"),
    Description("history_cost_14d", "Estimated ventilation cost selected period", lambda d: d["history_summary"]["cost"], "€", "mdi:currency-eur"),
    Description("estimated_moisture_generation_day_ml", "Estimated daily moisture generation", lambda d: d["estimated_moisture_generation_day_ml"], "mL", "mdi:water-plus"),
    Description("moisture_balance_today_ml", "Estimated moisture balance today", lambda d: d["moisture_balance_today_ml"], "mL", "mdi:scale-balance", step=10),
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
    # 0.26.4.7: what the room should do given the whole-house decision.
    ("house_aligned_action", "Recommendation", None, "mdi:home-switch-outline", None, True),
)


# 0.26.5.3 (recorder load): the forecast temperature change flickered between
# neighbouring tenths; it is published once it moved by 0.2 °C.
ROOM_DEADBAND = {"forecast_temperature_change_c": 0.2}


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
    # F10 (2026-10-16): produced for rooms without an opening contact
    # (coordinator) resp. part of the shared event vocabulary; formerly "unknown".
    "Ventilate indirectly": "ventilate_indirectly",
    "Open fully": "open_fully",
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


# 0.26.5.1 (community: the automation editor only offered "any state /
# unavailable / unknown" for the action entity): the state sensors declare
# their fixed vocabulary as an enum, so state triggers and conditions offer
# the translated states. The values themselves are unchanged ("unknown" stays
# a regular option).
ROOM_ENUM_OPTIONS: dict[str, list[str]] = {
    "action": [*dict.fromkeys(ACTION_STATE_MAP.values()), "unknown"],
    "house_aligned_action": [*sorted(HOUSE_ALIGNED_STATES), "unknown"],
    "mould_level": list(dict.fromkeys(MOULD_STATE_MAP.values())),
    "learning_status": list(dict.fromkeys(LEARNING_STATE_MAP.values())),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = get_runtime_coordinator(hass, entry)
    entities = [HouseSensor(coordinator, entry, desc) for desc in HOUSE]
    room_entities: dict[str, list[Any]] = {}
    for room in entry.data.get("rooms", []):
        for field, label, unit, icon, device_class, enabled_default in ROOM_FIELDS:
            room_entities.setdefault(room["key"], []).append(
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
    # 0.26.4.9: each room's entities belong to the room's sub-entry.
    add_entities_by_room(async_add_entities, entry, entities, room_entities)


class HouseSensor(FreshAirIQEntity, SensorEntity):
    # Dashboard transport attributes are intentionally live-only. They can contain
    # room/history/learning payloads larger than Home Assistant recorder's 16 KiB
    # state-attribute limit. MATCH_ALL keeps the complete live state available to
    # the FreshAirIQ dashboard while preventing recorder writes and warning spam.
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry, desc: Description) -> None:
        # translation_key must exist before the base entity decides whether a fallback
        # English name is needed. Otherwise Home Assistant keeps that fallback name
        # and never renders the localized entity name from translations/<lang>.json.
        self._attr_translation_key = desc.key
        super().__init__(coordinator, entry, desc.key, desc.name)
        self.desc = desc
        self._attr_native_unit_of_measurement = desc.unit
        self._attr_device_class = desc.device_class
        self._attr_entity_registry_enabled_default = desc.enabled_default

    @property
    def native_value(self) -> object:
        value = self.desc.value(self.coordinator.data)
        if self.desc.step:
            return quantized(value, self.desc.step)
        if self.desc.deadband:
            value = with_deadband(getattr(self, "_published", None), value, self.desc.deadband)
            self._published = value
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.desc.key == "status":
            # 0.26.5.3 (recorder load): the dashboard state travels over the live
            # channel (dashboard_live); the sensor keeps a small, stable summary,
            # so it writes a recorder row only when the status itself changes.
            attributes = {
                "status": self.coordinator.data.get("status"),
                "status_text": self.coordinator.data["status_text"],
                "freshairiq_transport": "status_v2",
                "freshairiq_live_api": LIVE_API,
                "freshairiq_details_api": DETAILS_API,
                "freshairiq_entry_id": self._entry.entry_id,
                "freshairiq_version": VERSION,
                "output_language": self.coordinator.data.get("output_language", "de"),
                "version": VERSION,
            }
            self.coordinator.runtime_health.observe_attribute_payload(
                "status", attributes, recorder_exposed=MATCH_ALL not in self._unrecorded_attributes
            )
            return attributes
        return None


class RoomSensor(FreshAirIQEntity, SensorEntity):
    # The complete per-room payload is dashboard transport, not recorder history.
    # Keep it live in the state machine, but exclude it from database attributes.
    _unrecorded_attributes = frozenset({"freshairiq_room_payload"})

    def __init__(
        self, coordinator: FreshAirIQCoordinator, entry: FreshAirIQConfigEntry,
        room_key: str, room_name: str, field: str, label: str, unit: str | None,
        icon: str | None, device_class: SensorDeviceClass | None = None,
        enabled_default: bool = True,
    ) -> None:
        # Entity name is only the measurement; the device supplies the room name.
        # Set the translation key before the base constructor so it does not persist
        # the English fallback label as the entity name.
        self._attr_translation_key = field
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
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if field in ROOM_ENUM_OPTIONS:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(ROOM_ENUM_OPTIONS[field])
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> object:
        value = self.coordinator.data["rooms"].get(self.room_key, {}).get(self.field)
        if self.field == "action":
            return ACTION_STATE_MAP.get(value, "unknown")
        if self.field == "house_aligned_action":
            return value if value in HOUSE_ALIGNED_STATES else "unknown"
        if self.field == "mould_level":
            return MOULD_STATE_MAP.get(value, "unknown")
        if self.field == "learning_status":
            return LEARNING_STATE_MAP.get(value, "base_estimate")
        if self.field in ROOM_DEADBAND:
            value = with_deadband(getattr(self, "_published", None), value, ROOM_DEADBAND[self.field])
            self._published = value
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
                payload, self._held_source = hold_source_details(stable_room_payload(room), getattr(self, "_held_source", None))
                attributes = {
                    # 0.26.5.3: without per-cycle counters (report times instead)
                    "freshairiq_room_payload": payload,
                    "freshairiq_room_key": self.room_key,
                    "freshairiq_transport": "room_v2",
                    "freshairiq_entry_id": self._entry.entry_id,
                    "freshairiq_version": VERSION,
                    "output_language": self.coordinator.data.get("output_language", "de"),  # 0.26.5.0: the dashboard speaks this language
                }
                self.coordinator.runtime_health.observe_attribute_payload(
                    "room_action", attributes,
                    recorder_exposed="freshairiq_room_payload" not in self._unrecorded_attributes,
                )
                return attributes
        return None

    @property
    def available(self) -> bool:
        room = self.coordinator.data.get("rooms", {}).get(self.room_key)
        return super().available and bool(room) and room.get("data_quality") == "ok"
