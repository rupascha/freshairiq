"""Config and options flows for FreshAirIQ."""
from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    selector,
)

from .const import *
from .settings_contract import native_option_key
from .notifications import _all_notification_targets, _available_notification_targets, _send_targets
from .room_creation_trace import trace_room_creation, trace_room_creation_after_reload
from .validation import option_relationship_error


_RUNTIME_LISTENER_OPTION_KEYS = {
    "adult_presence_entities",
    "child_presence_entities",
    "presence_sensor_entities",
    "pet_safe_presence_entities",
    "voc_sensor_enabled",
    "pm25_sensor_enabled",
    "illuminance_sensor_enabled",
}
_RUNTIME_LISTENER_DATA_KEYS = {
    CONF_OUTDOOR_WEATHER,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_POLLEN_ENTITY,
}

_RESIDENT_PROFILE_STORAGE_KEY = native_option_key("resident_room_profiles")


def _slug(name: str) -> str:
    value = name.lower().strip().translate(str.maketrans("äöüß", "aous"))
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "room"


def _entity_list(value: Any) -> list[str]:
    """Normalise legacy single-entity values for multi-entity selectors."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return list(dict.fromkeys(str(item) for item in value if item))
    return []


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, fallback: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    """Return a finite integer for persisted/config-flow values.

    Config entries can outlive entity/schema changes for years. Treat all
    persisted numeric values as untrusted so one corrupt legacy field cannot
    make the entire options or reconfigure flow unopenable.
    """
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        number = float(fallback)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(fallback)
    result = int(number)
    if minimum is not None:
        result = max(result, minimum)
    if maximum is not None:
        result = min(result, maximum)
    return result


def _required(key: str, value: Any = None):
    return vol.Required(key, default=value) if value not in (None, "") else vol.Required(key)


def _optional(key: str, value: Any = None):
    """Optional field prefill that stays genuinely clearable.

    ``default=`` is re-injected by voluptuous when HA omits a cleared optional
    selector. ``suggested_value`` pre-fills the UI without resurrecting the old
    value on submit, so remove → save really removes the entity/value.
    """
    return vol.Optional(key, description={"suggested_value": value}) if value not in (None, "") else vol.Optional(key)



def _time_default(value: Any, default: str) -> str:
    if isinstance(value, str) and ":" in value:
        parts = value.split(":", 1)
        try:
            return f"{int(parts[0])%24:02d}:{int(parts[1])%60:02d}"
        except (TypeError, ValueError):
            return default
    try:
        return f"{int(value)%24:02d}:00"
    except (TypeError, ValueError):
        return default

def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    """Build a HA number selector without serialising a null unit.

    Some Home Assistant releases reject ``unit_of_measurement: null`` while
    rendering config-flow selectors.  Only include the field when a real unit
    is supplied.
    """
    config = {
        "min": minimum,
        "max": maximum,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(**config))


def _outdoor_configuration_error(data: dict[str, Any]) -> str | None:
    """Validate an optional outdoor source without forcing setup up front.

    FreshAirIQ may be installed as an empty shell so the dashboard is available
    immediately. If no weather entity is configured, a manually selected
    outdoor temperature/humidity source must still be a complete pair.
    """
    if data.get(CONF_OUTDOOR_WEATHER):
        return None
    has_temperature = bool(data.get(CONF_OUTDOOR_TEMPERATURE))
    has_humidity = bool(data.get(CONF_OUTDOOR_HUMIDITY))
    return "outdoor_pair_required" if has_temperature != has_humidity else None


def _outdoor_schema(data: dict[str, Any] | None = None) -> vol.Schema:
    data = data or {}
    return vol.Schema({
        _optional(CONF_OUTDOOR_WEATHER, data.get(CONF_OUTDOOR_WEATHER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        _optional(CONF_OUTDOOR_TEMPERATURE, data.get(CONF_OUTDOOR_TEMPERATURE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        _optional(CONF_OUTDOOR_HUMIDITY, data.get(CONF_OUTDOOR_HUMIDITY)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
        ),
        _optional(CONF_POLLEN_ENTITY, data.get(CONF_POLLEN_ENTITY)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    })


def _available_room_goals(room: dict[str, Any]) -> list[str]:
    """Goals available from this room's configured data sources."""
    goals: list[str] = []
    if room.get(CONF_ROOM_HUMIDITY) and room.get(CONF_ROOM_TEMPERATURE):
        goals.append("humidity")
    if room.get(CONF_ROOM_CO2):
        goals.append("co2")
    if room.get(CONF_ROOM_CLIMATE) or room.get(CONF_ROOM_TARGET_TEMPERATURE) not in (None, "") or room.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK) not in (None, ""):
        goals.append("temperature")
    return goals


def _filter_room_priorities(value: Any, room: dict[str, Any]) -> list[str]:
    available = _available_room_goals(room)
    vals = value if isinstance(value, list) else []
    ordered = list(dict.fromkeys(str(x) for x in vals if str(x) in available))
    return ordered + [x for x in available if x not in ordered]

def _goal_priority_schema(room: dict[str, Any], *, include_back: bool = False) -> vol.Schema:
    """Show every available ventilation goal at once in its current priority order."""
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    if not current:
        return vol.Schema({})
    options = list(current)
    fields: dict[Any, Any] = {}
    if include_back:
        fields[vol.Optional("wizard_back", default=False)] = bool
    for idx, goal in enumerate(current, start=1):
        fields[vol.Required(f"goal_priority_{idx}", default=goal)] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="ventilation_goal",
            )
        )
    return vol.Schema(fields)


def _ranked_goal_priorities(user_input: dict[str, Any], room: dict[str, Any]) -> list[str]:
    """Return the complete, duplicate-free ranking submitted by the user."""
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    ranked = [
        str(user_input.get(f"goal_priority_{idx}") or "")
        for idx in range(1, len(current) + 1)
    ]
    if not any(ranked):
        return current
    if len(ranked) != len(current) or set(ranked) != set(current):
        return current
    return ranked


def _goal_priority_errors(user_input: dict[str, Any], room: dict[str, Any]) -> dict[str, str]:
    """Reject duplicate/missing ranked goals instead of throwing during persistence."""
    current = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
    ranked = [
        str(user_input.get(f"goal_priority_{idx}") or "")
        for idx in range(1, len(current) + 1)
    ]
    if not current or bool(user_input.get("wizard_back")):
        return {}
    if len(ranked) != len(current) or any(goal not in current for goal in ranked):
        return {"base": "invalid_goal_order"}
    if len(set(ranked)) != len(ranked):
        return {"base": "duplicate_goal_order"}
    return {}


# Legacy room-level reference keys remain readable for migration only: CONF_ROOM_REFERENCE_TEMPERATURE, CONF_ROOM_REFERENCE_HUMIDITY
def _room_schema(room: dict[str, Any] | None = None, levels: list[str] | None = None) -> vol.Schema:
    room = room or {}
    levels = list(dict.fromkeys(levels or []))
    return vol.Schema({
        _required(CONF_ROOM_NAME, room.get(CONF_ROOM_NAME)): selector.TextSelector(),
        _optional(CONF_ROOM_ICON, room.get(CONF_ROOM_ICON)): selector.IconSelector(),
        _optional(CONF_ROOM_TEMPERATURE, _entity_list(room.get(CONF_ROOM_TEMPERATURE))): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)
        ),
        _optional(CONF_ROOM_HUMIDITY, _entity_list(room.get(CONF_ROOM_HUMIDITY))): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="humidity", multiple=True)
        ),
        vol.Required(CONF_ROOM_TEMPERATURE_AGGREGATION, default=str(room.get(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["mean", "median", "max", "min"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="climate_aggregation")),
        vol.Required(CONF_ROOM_HUMIDITY_AGGREGATION, default=str(room.get(CONF_ROOM_HUMIDITY_AGGREGATION, "mean"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["mean", "median", "max", "min"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="climate_aggregation")),
        vol.Optional(CONF_ROOM_CONTACTS, default=room.get(CONF_ROOM_CONTACTS, [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["binary_sensor", "sensor", "input_select", "select"], multiple=True)
        ),
        vol.Required(CONF_CONTACT_MODE, default=room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[CONTACT_MODE_ANY, CONTACT_MODE_ALL], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="contact_mode")
        ),
        # No volume-mode selector: users may provide a direct m³ value OR dimensions.
        _optional(CONF_ROOM_VOLUME, room.get(CONF_ROOM_VOLUME)): _number(2, 1000, 0.1, "m³"),
        _optional(CONF_ROOM_LENGTH, room.get(CONF_ROOM_LENGTH)): _number(0.5, 100, 0.01, "m"),
        _optional(CONF_ROOM_WIDTH, room.get(CONF_ROOM_WIDTH)): _number(0.5, 100, 0.01, "m"),
        _optional(CONF_ROOM_HEIGHT, room.get(CONF_ROOM_HEIGHT)): _number(1, 20, 0.01, "m"),
        _optional(CONF_ROOM_CO2, room.get(CONF_ROOM_CO2)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide")
        ),
        vol.Required(CONF_ROOM_TARGET_TEMPERATURE_MODE, default=str(room.get(CONF_ROOM_TARGET_TEMPERATURE_MODE, "automatic"))): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["automatic", "manual"], mode=selector.SelectSelectorMode.DROPDOWN)
        ),
        _optional(CONF_ROOM_TARGET_TEMPERATURE, room.get(CONF_ROOM_TARGET_TEMPERATURE)): _number(12, 30, 0.5, "°C"),
        _optional(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK, room.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK)): _number(12, 30, 0.5, "°C"),
        _optional(CONF_ROOM_VOC, room.get(CONF_ROOM_VOC)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["volatile_organic_compounds", "volatile_organic_compounds_parts"])
        ),
        _optional(CONF_ROOM_PM25, room.get(CONF_ROOM_PM25)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="pm25")
        ),
        _optional(CONF_ROOM_ILLUMINANCE, room.get(CONF_ROOM_ILLUMINANCE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="illuminance")
        ),
        _optional(CONF_ROOM_CLIMATE, room.get(CONF_ROOM_CLIMATE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        _optional(CONF_ROOM_EXHAUST_FAN, _entity_list(room.get(CONF_ROOM_EXHAUST_FAN))): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"], multiple=True)
        ),
        _optional(CONF_ROOM_SUPPLY_FAN, room.get(CONF_ROOM_SUPPLY_FAN)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
        _optional(CONF_ROOM_VENTILATION_DEVICE, room.get(CONF_ROOM_VENTILATION_DEVICE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
        _optional(CONF_ROOM_DEHUMIDIFIER, room.get(CONF_ROOM_DEHUMIDIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["humidifier", "fan", "switch"])
        ),
        _optional(CONF_ROOM_HUMIDIFIER, room.get(CONF_ROOM_HUMIDIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["humidifier", "fan", "switch"])
        ),
        _optional(CONF_ROOM_AIR_PURIFIER, room.get(CONF_ROOM_AIR_PURIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
        vol.Optional(CONF_ROOM_FLOOR, default=room.get(CONF_ROOM_FLOOR, "")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=levels, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=True, translation_key="floor")
        ),
        vol.Required(CONF_ROOM_INCLUDE_CALCULATIONS, default=bool(room.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))): bool,
        vol.Optional(CONF_ROOM_MOISTURE_SOURCES, default=room.get(CONF_ROOM_MOISTURE_SOURCES, [])): selector.SelectSelector(
            selector.SelectSelectorConfig(options=MOISTURE_SOURCES, multiple=True, mode=selector.SelectSelectorMode.LIST, translation_key="moisture_source")
        ),
        vol.Required(CONF_ROOM_THRESHOLD_MODE, default=_choice(room.get(CONF_ROOM_THRESHOLD_MODE), ROOM_THRESHOLD_AUTOMATIC, [ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED])): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="room_threshold_mode")
        ),
        vol.Required(CONF_ROOM_THRESHOLD_PERCENT, default=_bounded(room.get(CONF_ROOM_THRESHOLD_PERCENT), 5, 1, 30)): _number(1, 30, 0.5, "%"),
        vol.Required(CONF_ROOM_THRESHOLD_ML, default=_bounded(room.get(CONF_ROOM_THRESHOLD_ML), 100, 10, 1000)): _number(10, 1000, 10, "mL"),
    })


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten one level of HA data-entry sections into a normal mapping."""
    flat: dict[str, Any] = {}
    for key, value in dict(user_input).items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _room_section_schema(room: dict[str, Any] | None = None, levels: list[str] | None = None) -> vol.Schema:
    """Mobile-first room form grouped into short, collapsible sections."""
    room = room or {}
    levels = list(dict.fromkeys(levels or []))
    return vol.Schema({
        vol.Required("identity"): section(vol.Schema({
            _required(CONF_ROOM_NAME, room.get(CONF_ROOM_NAME)): selector.TextSelector(),
            _optional(CONF_ROOM_ICON, room.get(CONF_ROOM_ICON)): selector.IconSelector(),
            vol.Optional(CONF_ROOM_FLOOR, default=room.get(CONF_ROOM_FLOOR, "")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=levels, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=True, translation_key="floor")
            ),
            vol.Required(CONF_ROOM_INCLUDE_CALCULATIONS, default=bool(room.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))): bool,
        }), {"collapsed": False}),
        vol.Optional("properties"): section(vol.Schema({
            vol.Optional(CONF_ROOM_MOISTURE_SOURCES, default=room.get(CONF_ROOM_MOISTURE_SOURCES, [])): selector.SelectSelector(
                selector.SelectSelectorConfig(options=MOISTURE_SOURCES, multiple=True, mode=selector.SelectSelectorMode.LIST, translation_key="moisture_source")
            ),
            vol.Required(CONF_ROOM_THRESHOLD_MODE, default=_choice(room.get(CONF_ROOM_THRESHOLD_MODE), ROOM_THRESHOLD_AUTOMATIC, [ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED])): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="room_threshold_mode")
            ),
            vol.Required(CONF_ROOM_THRESHOLD_PERCENT, default=_bounded(room.get(CONF_ROOM_THRESHOLD_PERCENT), 5, 1, 30)): _number(1, 30, 0.5, "%"),
            vol.Required(CONF_ROOM_THRESHOLD_ML, default=_bounded(room.get(CONF_ROOM_THRESHOLD_ML), 100, 10, 1000)): _number(10, 1000, 10, "mL"),
        }), {"collapsed": True}),
        vol.Required("sensors"): section(vol.Schema({
            _optional(CONF_ROOM_TEMPERATURE, _entity_list(room.get(CONF_ROOM_TEMPERATURE))): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)
            ),
            _optional(CONF_ROOM_HUMIDITY, _entity_list(room.get(CONF_ROOM_HUMIDITY))): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity", multiple=True)
            ),
            vol.Required(CONF_ROOM_TEMPERATURE_AGGREGATION, default=str(room.get(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["mean", "median", "max", "min"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="climate_aggregation")),
            vol.Required(CONF_ROOM_HUMIDITY_AGGREGATION, default=str(room.get(CONF_ROOM_HUMIDITY_AGGREGATION, "mean"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["mean", "median", "max", "min"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="climate_aggregation")),
            vol.Optional(CONF_ROOM_CONTACTS, default=room.get(CONF_ROOM_CONTACTS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "sensor", "input_select", "select"], multiple=True)
            ),
            vol.Required(CONF_CONTACT_MODE, default=room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[CONTACT_MODE_ANY, CONTACT_MODE_ALL], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="contact_mode")
            ),
            _optional(CONF_ROOM_CO2, room.get(CONF_ROOM_CO2)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide")
            ),
            _optional(CONF_ROOM_EXHAUST_FAN, _entity_list(room.get(CONF_ROOM_EXHAUST_FAN))): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["fan", "switch"], multiple=True)
            ),
            _optional(CONF_ROOM_CLIMATE, room.get(CONF_ROOM_CLIMATE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            vol.Required(CONF_ROOM_TARGET_TEMPERATURE_MODE, default=str(room.get(CONF_ROOM_TARGET_TEMPERATURE_MODE, "automatic"))): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["automatic", "manual"], mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            _optional(CONF_ROOM_TARGET_TEMPERATURE, room.get(CONF_ROOM_TARGET_TEMPERATURE)): _number(12, 30, 0.5, "°C"),
            _optional(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK, room.get(CONF_ROOM_TARGET_TEMPERATURE_FALLBACK)): _number(12, 30, 0.5, "°C"),
        }), {"collapsed": False}),
        vol.Required("geometry"): section(vol.Schema({
            _optional(CONF_ROOM_VOLUME, room.get(CONF_ROOM_VOLUME)): _number(2, 1000, 0.1, "m³"),
            _optional(CONF_ROOM_LENGTH, room.get(CONF_ROOM_LENGTH)): _number(0.5, 100, 0.01, "m"),
            _optional(CONF_ROOM_WIDTH, room.get(CONF_ROOM_WIDTH)): _number(0.5, 100, 0.01, "m"),
            _optional(CONF_ROOM_HEIGHT, room.get(CONF_ROOM_HEIGHT)): _number(1, 20, 0.01, "m"),
        }), {"collapsed": True}),
        vol.Optional("optional_sensors"): section(vol.Schema({
            _optional(CONF_ROOM_VOC, room.get(CONF_ROOM_VOC)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class=["volatile_organic_compounds", "volatile_organic_compounds_parts"])
            ),
            _optional(CONF_ROOM_PM25, room.get(CONF_ROOM_PM25)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="pm25")
            ),
            _optional(CONF_ROOM_ILLUMINANCE, room.get(CONF_ROOM_ILLUMINANCE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="illuminance")
            ),
        }), {"collapsed": True}),
        vol.Optional("optional_actuators"): section(vol.Schema({
            _optional(CONF_ROOM_SUPPLY_FAN, room.get(CONF_ROOM_SUPPLY_FAN)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
            _optional(CONF_ROOM_VENTILATION_DEVICE, room.get(CONF_ROOM_VENTILATION_DEVICE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
            _optional(CONF_ROOM_DEHUMIDIFIER, room.get(CONF_ROOM_DEHUMIDIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["humidifier", "fan", "switch"])
        ),
            _optional(CONF_ROOM_HUMIDIFIER, room.get(CONF_ROOM_HUMIDIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["humidifier", "fan", "switch"])
        ),
            _optional(CONF_ROOM_AIR_PURIFIER, room.get(CONF_ROOM_AIR_PURIFIER)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["fan", "switch"])
        ),
        }), {"collapsed": True}),
    })


def _contact_reference_field(contact: str, kind: str) -> str:
    """Legacy key retained only for backwards compatibility with older flows."""
    return f"{contact}__freshairiq_reference_{kind}"


def _contact_display_name(hass, entity_id: str) -> str:
    """Return the user's HA entity name, with a readable entity-id fallback."""
    entity_id = str(entity_id or "").strip()
    state = hass.states.get(entity_id) if hass is not None else None
    friendly = str((state.attributes or {}).get("friendly_name") or "").strip() if state else ""
    if friendly:
        return friendly
    object_id = entity_id.split(".", 1)[-1] if "." in entity_id else entity_id
    readable = re.sub(r"[_-]+", " ", object_id).strip()
    return readable.title() if readable else entity_id


def _single_contact_reference_schema(room: dict[str, Any], contact: str) -> vol.Schema:
    """Static translated schema for exactly one real window/door contact."""
    temperatures = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidities = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    covers = room.get(CONF_CONTACT_COVERS) or {}
    passage_doors = room.get(CONF_CONTACT_PASSAGE_DOORS) or {}
    orientations = room.get(CONF_CONTACT_ORIENTATIONS) or {}
    delays = room.get(CONF_CONTACT_DELAYS) or {}
    temp = str(temperatures.get(contact) or "").strip()
    humidity = str(humidities.get(contact) or "").strip()
    fields: dict[Any, Any] = {
        (vol.Optional("reference_temperature", default=temp) if temp else vol.Optional("reference_temperature")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature")),
        (vol.Optional("reference_humidity", default=humidity) if humidity else vol.Optional("reference_humidity")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="humidity")),
        vol.Required("delay_seconds", default=_safe_int(delays.get(contact, room.get(CONF_CONTACT_DELAY, 0)), 0, minimum=0, maximum=600)):
            _number(0, 600, 1, "s"),
        vol.Required("orientation", default=str(orientations.get(contact, room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)))):
            selector.SelectSelector(selector.SelectSelectorConfig(options=ORIENTATIONS, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="window_orientation")),
        vol.Optional("covers", default=list(covers.get(contact) or [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="cover", multiple=True)),
        vol.Required("cover_position_zero_means", default=str(room.get("cover_position_zero_means", "closed"))):
            selector.SelectSelector(selector.SelectSelectorConfig(options=["closed", "open"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="cover_position_zero_means")),
        vol.Optional("passage_door", default=bool(passage_doors.get(contact, False))):
            selector.BooleanSelector(),
    }
    return vol.Schema(fields)


def _schema_with_wizard_back(schema: vol.Schema) -> vol.Schema:
    """Add the explicit previous-page control only to the editable room wizard."""
    fields = dict(schema.schema)
    fields[vol.Optional("wizard_back", default=False)] = selector.BooleanSelector()
    return vol.Schema(fields)


def _apply_single_contact_reference(
    room: dict[str, Any], contact: str, user_input: dict[str, Any]
) -> bool:
    """Persist one opening without touching metadata belonging to other openings."""
    temp = str(user_input.get("reference_temperature") or "").strip()
    humidity = str(user_input.get("reference_humidity") or "").strip()
    if bool(temp) != bool(humidity):
        return False

    temperatures = dict(room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {})
    humidities = dict(room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {})
    contact_covers = dict(room.get(CONF_CONTACT_COVERS) or {})
    passage_doors = dict(room.get(CONF_CONTACT_PASSAGE_DOORS) or {})
    orientations = dict(room.get(CONF_CONTACT_ORIENTATIONS) or {})
    delays = dict(room.get(CONF_CONTACT_DELAYS) or {})

    if temp and humidity:
        temperatures[contact] = temp
        humidities[contact] = humidity
    else:
        temperatures.pop(contact, None)
        humidities.pop(contact, None)

    raw_covers = user_input.get("covers") or []
    if isinstance(raw_covers, str):
        raw_covers = [raw_covers]
    selected_covers = [
        str(entity_id) for entity_id in raw_covers if str(entity_id).startswith("cover.")
    ]
    if selected_covers:
        contact_covers[contact] = list(dict.fromkeys(selected_covers))
    else:
        contact_covers.pop(contact, None)

    orientations[contact] = str(user_input.get("orientation", orientations.get(contact, ORIENTATION_UNKNOWN)) or ORIENTATION_UNKNOWN)
    delays[contact] = _safe_int(user_input.get("delay_seconds", delays.get(contact, 0)), 0, minimum=0, maximum=600)
    passage_doors[contact] = bool(user_input.get("passage_door", False))
    room[CONF_CONTACT_REFERENCE_TEMPERATURES] = temperatures
    room[CONF_CONTACT_REFERENCE_HUMIDITIES] = humidities
    room[CONF_CONTACT_COVERS] = contact_covers
    room[CONF_CONTACT_ORIENTATIONS] = orientations
    room[CONF_CONTACT_DELAYS] = delays
    room["cover_position_zero_means"] = str(user_input.get("cover_position_zero_means", room.get("cover_position_zero_means", "closed")) or "closed")
    room[CONF_CONTACT_PASSAGE_DOORS] = passage_doors
    return True



def _normalise_room(user_input: dict[str, Any], existing_rooms: list[dict[str, Any]], *, keep_key: str | None = None) -> tuple[dict[str, Any] | None, dict[str, str]]:
    user_input = _flatten_sections(user_input)
    errors: dict[str, str] = {}
    contacts = user_input.get(CONF_ROOM_CONTACTS) or []
    if isinstance(contacts, str):
        contacts = [contacts]
    include = bool(user_input.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))
    # A room may intentionally be created before any sensors are installed.
    # Keep it as a configured/passive room and activate calculations later,
    # once the required temperature, humidity and opening contacts exist.
    has_temperature = bool(user_input.get(CONF_ROOM_TEMPERATURE))
    has_humidity = bool(user_input.get(CONF_ROOM_HUMIDITY))
    if include and not has_temperature and not has_humidity and not contacts:
        include = False
    if include and not has_temperature:
        errors[CONF_ROOM_TEMPERATURE] = "required"
    if include and not has_humidity:
        errors[CONF_ROOM_HUMIDITY] = "required"
    # Opening contacts are optional for calculated indoor rooms. A room with
    # temperature + humidity remains part of the house model even when it has
    # no own/assigned opening. Contacts describe *how* FreshAirIQ can observe a
    # ventilation path; they are not a prerequisite for climate calculation.

    volume = _number_or_none(user_input.get(CONF_ROOM_VOLUME))
    length = _number_or_none(user_input.get(CONF_ROOM_LENGTH))
    width = _number_or_none(user_input.get(CONF_ROOM_WIDTH))
    height = _number_or_none(user_input.get(CONF_ROOM_HEIGHT))
    dimensions_complete = all(v is not None and v > 0 for v in (length, width, height))
    # Geometry is required only for rooms that actively participate in the
    # physical moisture/ventilation model. Passive/imported planning rooms may
    # be saved without invented dimensions and completed later.
    if include:
        if volume is None and not dimensions_complete:
            errors["base"] = "room_volume_required"
        elif volume is not None and volume < 2:
            errors[CONF_ROOM_VOLUME] = "room_volume_too_small"
        elif volume is None and dimensions_complete and (length * width * height) < 2:
            errors["base"] = "room_volume_too_small"
    else:
        # If passive-room geometry was supplied, still reject impossible values
        # instead of silently persisting malformed physical metadata.
        if volume is not None and volume < 2:
            errors[CONF_ROOM_VOLUME] = "room_volume_too_small"
        elif volume is None and any(v is not None for v in (length, width, height)) and not dimensions_complete:
            errors["base"] = "room_dimensions_incomplete"
        elif volume is None and dimensions_complete and (length * width * height) < 2:
            errors["base"] = "room_volume_too_small"

    name = str(user_input.get(CONF_ROOM_NAME, "")).strip()
    if not name:
        errors[CONF_ROOM_NAME] = "room_name_required"
    if errors:
        return None, errors

    if keep_key:
        key = keep_key
    else:
        key = _slug(name)
        existing = {r["key"] for r in existing_rooms}
        original = key
        i = 2
        while key in existing:
            key = f"{original}_{i}"; i += 1

    previous = next((r for r in existing_rooms if r.get("key") == key), {})
    raw_sources = user_input.get(CONF_ROOM_MOISTURE_SOURCES, previous.get(CONF_ROOM_MOISTURE_SOURCES, [])) or []
    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]
    moisture_sources = [x for x in raw_sources if x in MOISTURE_SOURCES]
    room = {k: v for k, v in dict(user_input).items() if v not in (None, "")}
    for aggregation_key in (CONF_ROOM_TEMPERATURE_AGGREGATION, CONF_ROOM_HUMIDITY_AGGREGATION):
        if str(room.get(aggregation_key, "mean")) not in {"mean", "median", "min", "max"}:
            room[aggregation_key] = "mean"

    priorities = room.get(CONF_ROOM_GOAL_PRIORITIES, previous.get(CONF_ROOM_GOAL_PRIORITIES, []))
    priorities = _filter_room_priorities(priorities, room)

    room.update({
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_CONTACTS: list(contacts),
        CONF_CONTACT_MODE: room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY),
        CONF_ROOM_FLOOR: str(room.get(CONF_ROOM_FLOOR, "")).strip() or "Unzugeordnet",
        CONF_ROOM_WINDOW_ORIENTATION: room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN),
        CONF_ROOM_INCLUDE_CALCULATIONS: include,
        CONF_ROOM_MOISTURE_SOURCES: list(moisture_sources),
        CONF_ROOM_GOAL_PRIORITIES: priorities,
        CONF_ROOM_TARGET_TEMPERATURE_MODE: str(room.get(CONF_ROOM_TARGET_TEMPERATURE_MODE, previous.get(CONF_ROOM_TARGET_TEMPERATURE_MODE, "automatic"))),
        CONF_ROOM_THRESHOLD_MODE: _choice(room.get(CONF_ROOM_THRESHOLD_MODE), ROOM_THRESHOLD_AUTOMATIC, [ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED]),
        CONF_ROOM_THRESHOLD_PERCENT: _bounded(room.get(CONF_ROOM_THRESHOLD_PERCENT), 5, 1, 30),
        CONF_ROOM_THRESHOLD_ML: _bounded(room.get(CONF_ROOM_THRESHOLD_ML), 100, 10, 1000),
        CONF_ROOM_SORT_ORDER: _safe_int(previous.get(CONF_ROOM_SORT_ORDER), len(existing_rooms), minimum=0),
        CONF_CONTACT_DELAYS: dict(previous.get(CONF_CONTACT_DELAYS, {})),
        CONF_CONTACT_ORIENTATIONS: dict(previous.get(CONF_CONTACT_ORIENTATIONS, {})),
        CONF_CONTACT_REFERENCE_TEMPERATURES: dict(previous.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})),
        CONF_CONTACT_REFERENCE_HUMIDITIES: dict(previous.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})),
        CONF_CONTACT_COVERS: deepcopy(previous.get(CONF_CONTACT_COVERS, {})),
        "cover_position_zero_means": str(user_input.get("cover_position_zero_means", previous.get("cover_position_zero_means", "closed")) or "closed"),
        CONF_CONTACT_PASSAGE_DOORS: deepcopy(previous.get(CONF_CONTACT_PASSAGE_DOORS, {})),
    })
    # If all dimensions are present they are the source of truth; otherwise use
    # the direct m³ value. This keeps dimension-based rooms editable without a
    # separate and confusing "volume mode" selector.
    if dimensions_complete:
        room[CONF_ROOM_LENGTH] = length; room[CONF_ROOM_WIDTH] = width; room[CONF_ROOM_HEIGHT] = height
        room[CONF_ROOM_VOLUME] = round(length * width * height, 3)
    elif volume is not None:
        room[CONF_ROOM_VOLUME] = round(volume, 3)
        room.pop(CONF_ROOM_LENGTH, None); room.pop(CONF_ROOM_WIDTH, None); room.pop(CONF_ROOM_HEIGHT, None)
    else:
        # Passive/imported planning shell: no physical size is known yet.
        room.pop(CONF_ROOM_VOLUME, None); room.pop(CONF_ROOM_LENGTH, None); room.pop(CONF_ROOM_WIDTH, None); room.pop(CONF_ROOM_HEIGHT, None)

    # Room-wide reference-air fields were superseded by per-opening mappings.
    # Never write them back from current editors; coordinator migration fallback
    # remains able to read legacy entries until each opening is migrated.
    room.pop(CONF_ROOM_REFERENCE_TEMPERATURE, None)
    room.pop(CONF_ROOM_REFERENCE_HUMIDITY, None)
    # Remove delays for contacts no longer configured.
    room[CONF_CONTACT_DELAYS] = {c: _safe_int(room[CONF_CONTACT_DELAYS].get(c, previous.get(CONF_CONTACT_DELAY, 0)), 0, minimum=0, maximum=600) for c in contacts}
    room[CONF_CONTACT_ORIENTATIONS] = {c: str(room[CONF_CONTACT_ORIENTATIONS].get(c, room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN))) for c in contacts}
    room[CONF_CONTACT_REFERENCE_TEMPERATURES] = {
        c: str(room[CONF_CONTACT_REFERENCE_TEMPERATURES].get(c) or "").strip()
        for c in contacts if str(room[CONF_CONTACT_REFERENCE_TEMPERATURES].get(c) or "").strip()
    }
    room[CONF_CONTACT_REFERENCE_HUMIDITIES] = {
        c: str(room[CONF_CONTACT_REFERENCE_HUMIDITIES].get(c) or "").strip()
        for c in contacts if str(room[CONF_CONTACT_REFERENCE_HUMIDITIES].get(c) or "").strip()
    }
    room[CONF_CONTACT_COVERS] = {
        c: list(dict.fromkeys(str(entity_id) for entity_id in (room[CONF_CONTACT_COVERS].get(c) or []) if str(entity_id).startswith("cover.")))
        for c in contacts if room[CONF_CONTACT_COVERS].get(c)
    }
    room[CONF_CONTACT_PASSAGE_DOORS] = {c: bool(room.get(CONF_CONTACT_PASSAGE_DOORS, {}).get(c, False)) for c in contacts}
    return room, {}


def _normalise_legacy_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(dict(data))
    rooms: list[dict[str, Any]] = []
    for idx, old_room in enumerate(migrated.get(CONF_ROOMS, [])):
        room = dict(old_room)
        if CONF_ROOM_CONTACTS not in room:
            legacy_contact = room.get(CONF_ROOM_CONTACT)
            room[CONF_ROOM_CONTACTS] = [legacy_contact] if legacy_contact else []
        room.setdefault(CONF_CONTACT_MODE, CONTACT_MODE_ANY)
        room.setdefault(CONF_ROOM_FLOOR, FLOOR_GROUND)
        room.setdefault(CONF_ROOM_SORT_ORDER, idx)
        room.setdefault(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        room.setdefault(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)
        room.setdefault(CONF_ROOM_MOISTURE_SOURCES, [])
        room[CONF_ROOM_GOAL_PRIORITIES] = _filter_room_priorities(room.get(CONF_ROOM_GOAL_PRIORITIES, []), room)
        room.setdefault(CONF_ROOM_TARGET_TEMPERATURE_MODE, "automatic")
        room.setdefault(CONF_ROOM_TEMPERATURE_AGGREGATION, "mean")
        room.setdefault(CONF_ROOM_HUMIDITY_AGGREGATION, "mean")
        room.setdefault(CONF_ROOM_THRESHOLD_MODE, ROOM_THRESHOLD_AUTOMATIC)
        room.setdefault(CONF_ROOM_THRESHOLD_PERCENT, 5.0)
        room.setdefault(CONF_ROOM_THRESHOLD_ML, 100.0)
        room.setdefault(CONF_CONTACT_DELAYS, {c: _safe_int(room.get(CONF_CONTACT_DELAY, 0), 0, minimum=0, maximum=600) for c in room.get(CONF_ROOM_CONTACTS, [])})
        room.setdefault(CONF_CONTACT_ORIENTATIONS, {c: room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN) for c in room.get(CONF_ROOM_CONTACTS, [])})
        room.setdefault(CONF_CONTACT_REFERENCE_TEMPERATURES, {})
        room.setdefault(CONF_CONTACT_REFERENCE_HUMIDITIES, {})
        room.setdefault(CONF_CONTACT_COVERS, {})
        # Safe one-opening migration: when a legacy room had exactly one
        # window/door, its room-wide covers unambiguously belong to that opening.
        # With multiple openings we retain the legacy list only as a runtime
        # fallback and never guess a wrong physical assignment.
        contacts = list(room.get(CONF_ROOM_CONTACTS, []) or [])
        if not room.get(CONF_CONTACT_COVERS) and len(contacts) == 1 and room.get(CONF_ROOM_COVERS):
            room[CONF_CONTACT_COVERS] = {contacts[0]: list(room.get(CONF_ROOM_COVERS) or [])}
        room.pop(CONF_ROOM_CONTACT, None)
        rooms.append(room)
    migrated[CONF_ROOMS] = rooms
    return migrated




def _bounded(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    """Return a finite numeric default that is valid for a selector/schema range."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(fallback)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(fallback)
    return min(max(number, minimum), maximum)


def _choice(value: Any, fallback: str, allowed: list[str]) -> str:
    """Keep legacy/corrupt option values from breaking an options form."""
    value = str(value) if value is not None else fallback
    return value if value in allowed else fallback


_LEGACY_LEVEL_LABELS = {
    "basement": "Kellergeschoss",
    "base_floor": "Kellergeschoss",
    "base floor": "Kellergeschoss",
    "Basement": "Kellergeschoss",
    "ground_floor": "Erdgeschoss",
    "ground floor": "Erdgeschoss",
    "Ground Floor": "Erdgeschoss",
    "upper_floor": "Obergeschoss",
    "upper floor": "Obergeschoss",
    "Upper Floor": "Obergeschoss",
    "attic": "Dachgeschoss",
    "other": "Sonstiger Bereich",
}

_LEGACY_LEVEL_LABELS_EN = {
    "basement": "Basement",
    "base_floor": "Basement",
    "base floor": "Basement",
    "Basement": "Basement",
    "ground_floor": "Ground floor",
    "ground floor": "Ground floor",
    "Ground Floor": "Ground floor",
    "upper_floor": "Upper floor",
    "upper floor": "Upper floor",
    "Upper Floor": "Upper floor",
    "attic": "Attic",
    "other": "Other area",
    # Stored default for rooms without a floor; only the display is translated.
    "Unzugeordnet": "Unassigned",
}


def _is_de(language: Any) -> bool:
    """Home Assistant falls back to English for every non-German language."""
    return str(language or "de").lower().startswith("de")


def _flow_language(hass: Any) -> str:
    try:
        return str(hass.config.language or "en") if hass is not None else "de"
    except AttributeError:
        return "de"


def _txt(language: Any, de: str, en: str) -> str:
    return de if _is_de(language) else en


def _level_label(value: Any, language: Any = "de") -> str:
    """Human-readable label for legacy and user-defined levels/zones."""
    raw = str(value or "").strip()
    if _is_de(language):
        return _LEGACY_LEVEL_LABELS.get(raw, raw or "Nicht zugeordnet")
    return _LEGACY_LEVEL_LABELS_EN.get(raw, raw or "Unassigned")

def _level_options(levels: list[str], language: Any = "de") -> list[dict[str, str]]:
    return [{"value": x, "label": _level_label(x, language)} for x in levels]


_PROFILE_LABELS_DE = {
    PROFILE_DEHUMIDIFY: "Entfeuchten",
    PROFILE_COMFORT: "Komfort",
    PROFILE_SUMMER_COOLING: "Sommer kühlen",
}

_HEATING_LABELS_DE = {
    HEATING_HEAT_PUMP: "Wärmepumpe",
    HEATING_GAS: "Gasheizung",
    HEATING_DISTRICT: "Fernwärme",
    HEATING_ELECTRIC: "Elektroheizung",
    HEATING_OIL: "Ölheizung",
}

_PROFILE_LABELS_EN = {
    PROFILE_DEHUMIDIFY: "Dehumidify",
    PROFILE_COMFORT: "Comfort",
    PROFILE_SUMMER_COOLING: "Summer cooling",
}

_HEATING_LABELS_EN = {
    HEATING_HEAT_PUMP: "Heat pump",
    HEATING_GAS: "Gas heating",
    HEATING_DISTRICT: "District heating",
    HEATING_ELECTRIC: "Electric heating",
    HEATING_OIL: "Oil heating",
}

def _model_schema(current: dict[str, Any]) -> vol.Schema:
    """Advanced ventilation model grouped into understandable sections."""
    return vol.Schema({
        vol.Required("humidity_thresholds"): section(vol.Schema({
            vol.Required(native_option_key("start_rh"), default=_bounded(current.get("start_rh"), 62, 40, 90)): _number(40, 90, 1, "%"),
            vol.Required(native_option_key("high_rh"), default=_bounded(current.get("high_rh"), 68, 45, 95)): _number(45, 95, 1, "%"),
            vol.Required(native_option_key("target_rh"), default=_bounded(current.get("target_rh"), 58, 35, 75)): _number(35, 75, 1, "%"),
            vol.Required(native_option_key("min_delta"), default=_bounded(current.get("min_delta"), 2.5, .1, 8)): _number(0.1, 8, 0.1, "g/m³"),
            vol.Required(native_option_key("min_delta_high_rh"), default=_bounded(current.get("min_delta_high_rh"), 1.5, .1, 5)): _number(0.1, 5, 0.1, "g/m³"),
            vol.Required(native_option_key("close_delta"), default=_bounded(current.get("close_delta"), .4, -1, 3)): _number(-1, 3, 0.1, "g/m³"),
        }), {"collapsed": False}),
        vol.Required("recommendation_thresholds"): section(vol.Schema({
            # House-wide threshold mode/value has its own guided settings step so
            # Home Assistant never shows percentage and mL inputs at the same time.
            vol.Required(native_option_key("min_potential_room_ml"), default=_bounded(current.get("min_potential_room_ml"), 100, 10, 1000)): _number(10, 1000, 10, "mL"),
        }), {"collapsed": False}),
        vol.Required("ventilation_timing"): section(vol.Schema({
            vol.Required(native_option_key("min_duration_min"), default=_bounded(current.get("min_duration_min"), 3, 1, 30)): _number(1, 30, 1, "min"),
            vol.Required(native_option_key("max_duration_min"), default=_bounded(current.get("max_duration_min"), 20, 3, 90)): _number(3, 90, 1, "min"),
            vol.Required(native_option_key("post_ventilation_stabilization_min"), default=_bounded(current.get("post_ventilation_stabilization_min"), 4, 1, 15)): _number(1, 15, 1, "min"),
            vol.Required(native_option_key("repeat_recommendation_cooldown_min"), default=_bounded(current.get("repeat_recommendation_cooldown_min"), 20, 5, 120)): _number(5, 120, 5, "min"),
            vol.Required(native_option_key("repeat_min_benefit_ml"), default=_bounded(current.get("repeat_min_benefit_ml"), 80, 10, 1000)): _number(10, 1000, 10, "mL"),
        }), {"collapsed": True}),
        vol.Required("efficiency"): section(vol.Schema({
            vol.Required(native_option_key("min_return_next_5_min_ml"), default=_bounded(current.get("min_return_next_5_min_ml"), 25, 0, 500)): _number(0, 500, 5, "mL"),
            vol.Required(native_option_key("max_temp_loss_next_5_min_c"), default=_bounded(current.get("max_temp_loss_next_5_min_c"), .6, .1, 5)): _number(0.1, 5, 0.1, "°C"),
            vol.Required(native_option_key("min_efficiency_ml_per_01c"), default=_bounded(current.get("min_efficiency_ml_per_01c"), 8, 0, 200)): _number(0, 200, 1, "mL/0,1°C"),
        }), {"collapsed": True}),
        vol.Required("health_limits"): section(vol.Schema({
            vol.Required(native_option_key("surface_factor"), default=_bounded(current.get("surface_factor"), .25, .05, .8)): _number(0.05, 0.8, 0.05),
            vol.Required(native_option_key("mould_warn_surface_rh"), default=_bounded(current.get("mould_warn_surface_rh"), 80, 60, 95)): _number(60, 95, 1, "%"),
            vol.Required(native_option_key("mould_critical_surface_rh"), default=_bounded(current.get("mould_critical_surface_rh"), 90, 70, 100)): _number(70, 100, 1, "%"),
            vol.Required(native_option_key("co2_warn"), default=_bounded(current.get("co2_warn"), 1000, 600, 2500)): _number(600, 2500, 50, "ppm"),
            vol.Required(native_option_key("co2_critical"), default=_bounded(current.get("co2_critical"), 1400, 800, 4000)): _number(800, 4000, 50, "ppm"),
        }), {"collapsed": True}),
        vol.Required("learning"): section(vol.Schema({
            vol.Required(native_option_key("learning_enabled"), default=bool(current.get("learning_enabled", True))): bool,
            vol.Required(native_option_key("learning_max_duration_min"), default=_bounded(current.get("learning_max_duration_min"), 120, 15, 240)): _number(15, 240, 5, "min"),
        }), {"collapsed": True}),
    })


def _cross_ventilation_schema(current: dict[str, Any]) -> vol.Schema:
    """Explicit cross-ventilation topology; kept separate because syntax needs examples."""
    return vol.Schema({
        vol.Optional(native_option_key("cross_ventilation_pairs"), default=str(current.get("cross_ventilation_pairs") or "")): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
        vol.Optional(native_option_key("cross_zone_connections"), default=str(current.get("cross_zone_connections") or "")): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
    })

def _profile_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(native_option_key("operating_profile"), default=current["operating_profile"]): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[PROFILE_DEHUMIDIFY, PROFILE_COMFORT, PROFILE_SUMMER_COOLING], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="operating_profile")
        )
    })





def _profile_details_schema(current: dict[str, Any]) -> vol.Schema:
    profile = current.get("operating_profile", PROFILE_COMFORT)
    if profile == PROFILE_SUMMER_COOLING:
        return vol.Schema({
            vol.Required(native_option_key("cooling_start_temp_c"), default=current["cooling_start_temp_c"]): _number(18, 35, 0.5, "°C"),
            vol.Required(native_option_key("cooling_min_outdoor_delta_c"), default=current["cooling_min_outdoor_delta_c"]): _number(0.5, 10, 0.5, "°C"),
            vol.Required(native_option_key("cooling_max_indoor_rh"), default=current["cooling_max_indoor_rh"]): _number(40, 90, 1, "%"),
            vol.Required(native_option_key("cooling_max_moisture_gain_5min_ml"), default=current["cooling_max_moisture_gain_5min_ml"]): _number(0, 500, 5, "mL"),
        })
    if profile == PROFILE_DEHUMIDIFY:
        return vol.Schema({
            vol.Required(native_option_key("min_return_next_5_min_ml"), default=current.get("min_return_next_5_min_ml", 15.0)): _number(0, 500, 5, "mL"),
            vol.Required(native_option_key("max_temp_loss_next_5_min_c"), default=current.get("max_temp_loss_next_5_min_c", 1.0)): _number(0.1, 5, 0.1, "°C"),
            vol.Required(native_option_key("min_efficiency_ml_per_01c"), default=current.get("min_efficiency_ml_per_01c", 5.0)): _number(0, 200, 1, "mL/0,1°C"),
        })
    return vol.Schema({
        vol.Required(native_option_key("min_return_next_5_min_ml"), default=current.get("min_return_next_5_min_ml", 25.0)): _number(0, 500, 5, "mL"),
        vol.Required(native_option_key("max_temp_loss_next_5_min_c"), default=current.get("max_temp_loss_next_5_min_c", 0.6)): _number(0.1, 5, 0.1, "°C"),
        vol.Required(native_option_key("min_efficiency_ml_per_01c"), default=current.get("min_efficiency_ml_per_01c", 8.0)): _number(0, 200, 1, "mL/0,1°C"),
    })



def _building_schema(current: dict[str, Any]) -> vol.Schema:
    """Native building-only settings matching the dashboard gear structure."""
    return vol.Schema({
        vol.Required(
            native_option_key("property_type"),
            default=current.get("property_type", PROPERTY_HOUSE),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=PROPERTY_TYPES,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="property_type",
            )
        ),
    })


def _resident_name_list(value: Any) -> list[str]:
    text = str(value or "").replace(";", ",").replace("\n", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def _resident_slot_overview(options: dict[str, Any], language: str = "de") -> str:
    """Name each numbered profile slot, e.g. "Erwachsener 1 = Anna" (0.26.4.1).

    Home Assistant cannot put names into field labels, so the step description
    tells the user which numbered block belongs to whom.
    """
    de = str(language or "de").lower().startswith("de")  # HA falls back to English
    labels = {"adult": "Erwachsener" if de else "Adult", "child": "Kind" if de else "Child"}
    missing = "noch ohne Namen" if de else "no name yet"
    parts: list[str] = []
    for role, names_key, count_key in (("adult", "adult_resident_names", "adult_occupants"), ("child", "child_resident_names", "child_occupants")):
        names = _resident_name_list(options.get(names_key))
        try:
            count = int(float(options.get(count_key, 0) or 0))
        except (TypeError, ValueError):
            count = 0
        for idx in range(min(max(count, len(names)), 4)):
            name = names[idx] if idx < len(names) else missing
            parts.append(f"{labels[role]} {idx + 1} = {name}")
    return " · ".join(parts) if parts else ("keine Bewohner angelegt" if de else "no residents yet")


def _resident_slot_placeholders(options: dict[str, Any], language: str = "de") -> dict[str, str]:
    """Names for the numbered profile fields ("{adult_1} – Räume" -> "Anna – Räume").

    Home Assistant applies description placeholders to field labels, so every slot
    shown in the form must have a value; unnamed slots keep "Erwachsener 1".
    """
    de = str(language or "de").lower().startswith("de")  # HA falls back to English
    labels = {"adult": "Erwachsener" if de else "Adult", "child": "Kind" if de else "Child"}
    result: dict[str, str] = {}
    for role, names_key in (("adult", "adult_resident_names"), ("child", "child_resident_names")):
        names = _resident_name_list(options.get(names_key))
        for idx in range(4):
            result[f"{role}_{idx + 1}"] = names[idx] if idx < len(names) else f"{labels[role]} {idx + 1}"
    return result


def _resident_profiles_dict(value: Any) -> dict[str, dict[str, Any]]:
    import json
    if isinstance(value, dict):
        return {str(k): dict(v) for k, v in value.items() if isinstance(v, dict)}
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return {str(k): dict(v) for k, v in parsed.items() if isinstance(v, dict)} if isinstance(parsed, dict) else {}


def _residents_schema(current: dict[str, Any], rooms: list[dict[str, Any]] | None = None) -> vol.Schema:
    """Readable resident/presence/personalisation form; never expose profile JSON."""
    rooms = rooms or []
    room_options = [{"value": str(r.get("key")), "label": str(r.get(CONF_ROOM_NAME) or r.get("key"))} for r in rooms if r.get("key")]
    profiles = _resident_profiles_dict(current.get("resident_room_profiles"))
    adult_names = _resident_name_list(current.get("adult_resident_names"))
    child_names = _resident_name_list(current.get("child_resident_names"))
    profile_fields: dict[Any, Any] = {}
    for role, names, count in (("adult", adult_names, int(current.get("adult_occupants", 0) or 0)), ("child", child_names, int(current.get("child_occupants", 0) or 0))):
        total = min(max(count, len(names)), 4)
        for idx in range(total):
            profile = profiles.get(f"{role}:{idx}", {})
            prefix = f"{role}_{idx + 1}"
            profile_fields[vol.Optional(f"{prefix}_rooms", default=list(profile.get("room_keys") or []))] = selector.SelectSelector(selector.SelectSelectorConfig(options=room_options, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN))
            profile_fields[vol.Required(f"{prefix}_thermal", default=str(profile.get("thermal_preference") or "inherit"))] = selector.SelectSelector(selector.SelectSelectorConfig(options=["inherit", "warm", "balanced", "cool"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="resident_thermal_preference"))
            profile_fields[vol.Optional(f"{prefix}_notifications", default=", ".join(profile.get("notification_targets") or []))] = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT))
    return vol.Schema({
        vol.Required("residents"): section(vol.Schema({
            vol.Required(native_option_key("adult_occupants"), default=current.get("adult_occupants", 2)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=20, step=1, mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional(native_option_key("adult_resident_names"), default=str(current.get("adult_resident_names", ""))): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            vol.Optional(native_option_key("adult_presence_entities"), default=current.get("adult_presence_entities", [])): selector.EntitySelector(selector.EntitySelectorConfig(domain=["person", "device_tracker"], multiple=True)),
            vol.Required(native_option_key("child_occupants"), default=current.get("child_occupants", 0)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=20, step=1, mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional(native_option_key("child_resident_names"), default=str(current.get("child_resident_names", ""))): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            vol.Optional(native_option_key("child_presence_entities"), default=current.get("child_presence_entities", [])): selector.EntitySelector(selector.EntitySelectorConfig(domain=["person", "device_tracker"], multiple=True)),
            vol.Required(native_option_key("pets_in_household"), default=bool(current.get("pets_in_household", False))): bool,
        }), {"collapsed": False}),
        vol.Optional("presence"): section(vol.Schema({
            vol.Optional(native_option_key("presence_sensor_entities"), default=current.get("presence_sensor_entities", [])): selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)),
            vol.Optional(native_option_key("pet_safe_presence_entities"), default=current.get("pet_safe_presence_entities", [])): selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)),
            vol.Required(native_option_key("untracked_follow_household"), default=bool(current.get("untracked_follow_household", True))): bool,
        }), {"collapsed": True}),
        vol.Optional("personalisation"): section(vol.Schema({
            vol.Required(native_option_key("personalisation_enabled"), default=bool(current.get("personalisation_enabled", True))): bool,
            vol.Required(native_option_key("thermal_preference"), default=str(current.get("thermal_preference", "balanced"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["warm", "balanced", "cool"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="thermal_preference")),
            vol.Required(native_option_key("personal_priority"), default=str(current.get("personal_priority", "balanced"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["climate", "balanced", "energy"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="personal_priority")),
            vol.Required(native_option_key("night_window_preference"), default=str(current.get("night_window_preference", "automatic"))): selector.SelectSelector(selector.SelectSelectorConfig(options=["automatic", "closed", "allowed"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="night_window_preference")),
        }), {"collapsed": True}),
        vol.Optional("night"): section(vol.Schema({
            vol.Required(native_option_key("night_start_hour"), default=_time_default(current.get("night_start_hour", "22:00"), "22:00")): selector.TimeSelector(),
            vol.Required(native_option_key("night_end_hour"), default=_time_default(current.get("night_end_hour", "07:00"), "07:00")): selector.TimeSelector(),
            vol.Required(native_option_key("night_forecast_enabled"), default=bool(current.get("night_forecast_enabled", True))): bool,
        }), {"collapsed": True}),
        vol.Optional("resident_profiles"): section(vol.Schema(profile_fields), {"collapsed": True}),
    })


def _forecast_schema(current: dict[str, Any]) -> vol.Schema:
    """User-facing forecast horizon used consistently in dashboard and model output."""
    return vol.Schema({
        vol.Required(
            native_option_key("forecast_horizon_min"),
            default=int(round(_bounded(current.get("forecast_horizon_min"), 5, 1, 120))),
        ): _number(1, 120, 1, "min"),
    })

def _air_quality_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(native_option_key("voc_sensor_enabled"), default=bool(current.get("voc_sensor_enabled", True))): bool,
        vol.Required(native_option_key("pm25_sensor_enabled"), default=bool(current.get("pm25_sensor_enabled", True))): bool,
        vol.Required(native_option_key("illuminance_sensor_enabled"), default=bool(current.get("illuminance_sensor_enabled", True))): bool,
        vol.Required(native_option_key("pollen_enabled"), default=bool(current.get("pollen_enabled", False))): bool,
        vol.Required(native_option_key("pollen_max"), default=_bounded(current.get("pollen_max"), 4.0, 0, 10)): _number(0, 10, 0.5),
        vol.Required(native_option_key("pollen_strict_veto"), default=bool(current.get("pollen_strict_veto", True))): bool,
        vol.Required(native_option_key("wind_orientation_enabled"), default=bool(current.get("wind_orientation_enabled", True))): bool,
        vol.Required(native_option_key("voc_warn"), default=_bounded(current.get("voc_warn"), 600.0, 50, 5000)): _number(50, 5000, 50),
        vol.Required(native_option_key("voc_critical"), default=_bounded(current.get("voc_critical"), 1200.0, 100, 10000)): _number(100, 10000, 50),
        vol.Required(native_option_key("pm25_warn"), default=_bounded(current.get("pm25_warn"), 15.0, 1, 250)): _number(1, 250, 1, "µg/m³"),
        vol.Required(native_option_key("pm25_critical"), default=_bounded(current.get("pm25_critical"), 35.0, 2, 500)): _number(2, 500, 1, "µg/m³"),
        vol.Required(native_option_key("humidify_below_rh"), default=_bounded(current.get("humidify_below_rh"), 35.0, 20, 50)): _number(20, 50, 1, "%"),
        vol.Required(native_option_key("shade_above_temp_c"), default=_bounded(current.get("shade_above_temp_c"), 24.0, 18, 35)): _number(18, 35, 0.5, "°C"),
        vol.Required(native_option_key("shade_min_illuminance_lx"), default=_bounded(current.get("shade_min_illuminance_lx"), 10000.0, 0, 100000)): _number(0, 100000, 500, "lx"),
        vol.Required(native_option_key("cover_position_zero_means"), default=str(current.get("cover_position_zero_means", "closed"))): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["closed", "open"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="cover_position_zero_means")
        ),
        vol.Required(native_option_key("cover_learning_max_closed_percent"), default=_bounded(current.get("cover_learning_max_closed_percent"), 20.0, 0, 100)): _number(0, 100, 1, "%"),
    })



def _diagnostics_sharing_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(
            native_option_key("diagnostics_consent"),
            default=str(current.get("diagnostics_consent", "unset")),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["unset", "granted", "declined"],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="diagnostics_consent",
            )
        ),
        vol.Required(
            native_option_key("diagnostics_reporting_mode"),
            default=str(current.get("diagnostics_reporting_mode", "daily")),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["off", "errors", "daily", "weekly"],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="diagnostics_reporting_mode",
            )
        ),
        vol.Required(
            native_option_key("diagnostics_include_client_context"),
            default=bool(current.get("diagnostics_include_client_context", True)),
        ): bool,
    })

def _energy_system_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({vol.Required(native_option_key("heating_system"), default=current["heating_system"]): selector.SelectSelector(selector.SelectSelectorConfig(options=[HEATING_HEAT_PUMP, HEATING_GAS, HEATING_DISTRICT, HEATING_ELECTRIC, HEATING_OIL], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="heating_system"))})


def _energy_details_schema(current: dict[str, Any]) -> vol.Schema:
    system = current.get("heating_system", HEATING_HEAT_PUMP)
    if system == HEATING_HEAT_PUMP:
        return vol.Schema({
            vol.Required(native_option_key("electricity_price_per_kwh"), default=current.get("electricity_price_per_kwh", 0.30)): _number(0, 5, 0.01, "€/kWh"),
            vol.Required(native_option_key("heat_pump_cop"), default=current.get("heat_pump_cop", 3.5)): _number(1, 10, 0.1),
        })
    if system == HEATING_GAS:
        return vol.Schema({
            vol.Required(native_option_key("gas_price_per_kwh"), default=current.get("gas_price_per_kwh", 0.11)): _number(0, 2, 0.001, "€/kWh"),
            vol.Required(native_option_key("gas_efficiency"), default=current.get("gas_efficiency", 0.92)): _number(0.5, 1.0, 0.01),
        })
    if system == HEATING_OIL:
        return vol.Schema({
            vol.Required(native_option_key("oil_price_per_liter"), default=current.get("oil_price_per_liter", 1.0)): _number(0, 5, 0.01, "€/l"),
            vol.Required(native_option_key("oil_kwh_per_liter"), default=current.get("oil_kwh_per_liter", 10.0)): _number(8, 12, 0.1, "kWh/l"),
            vol.Required(native_option_key("oil_efficiency"), default=current.get("oil_efficiency", 0.88)): _number(0.5, 1.0, 0.01),
        })
    if system == HEATING_DISTRICT:
        return vol.Schema({
            vol.Required(native_option_key("district_price_per_kwh"), default=current.get("district_price_per_kwh", 0.15)): _number(0, 5, 0.01, "€/kWh"),
            vol.Required(native_option_key("district_efficiency"), default=current.get("district_efficiency", 0.98)): _number(0.5, 1.0, 0.01),
        })
    return vol.Schema({vol.Required(native_option_key("electricity_price_per_kwh"), default=current.get("electricity_price_per_kwh", 0.30)): _number(0, 5, 0.01, "€/kWh")})


def _notification_schema(hass, current: dict[str, Any], rooms: list[dict[str, Any]]) -> vol.Schema:
    services, entities = _available_notification_targets(hass, current.get("notification_targets", []))
    targets = [{"value": s, "label": f"notify.{s}"} for s in services]
    targets.extend({"value": f"entity:{entity_id}", "label": f"{entity_id} · notify.send_message"} for entity_id in entities)
    room_opts = [{"value": r["key"], "label": r.get("name", r["key"])} for r in rooms]
    return vol.Schema({
        vol.Required(native_option_key("notifications_enabled"), default=current["notifications_enabled"]): bool,
        vol.Optional(native_option_key("notification_targets"), default=current.get("notification_targets", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=targets, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(native_option_key("notification_scope"), default=current["notification_scope"]): selector.SelectSelector(selector.SelectSelectorConfig(options=[NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_BOTH], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="notification_scope")),
        vol.Optional(native_option_key("notification_room_keys"), default=current.get("notification_room_keys", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=room_opts, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(native_option_key("notify_ventilate"), default=current["notify_ventilate"]): bool,
        vol.Required(native_option_key("notify_close"), default=current["notify_close"]): bool,
        vol.Required(native_option_key("notify_complete"), default=current["notify_complete"]): bool,
        vol.Required(native_option_key("notify_cooling"), default=current["notify_cooling"]): bool,
        vol.Required(native_option_key("notify_mould"), default=current["notify_mould"]): bool,
        vol.Required(native_option_key("notify_sensor"), default=current["notify_sensor"]): bool,
        vol.Required(native_option_key("notify_night"), default=current["notify_night"]): bool,
        vol.Required(native_option_key("notify_learning"), default=current["notify_learning"]): bool,
        vol.Required(native_option_key("notification_cooldown_min"), default=current["notification_cooldown_min"]): _number(10, 1440, 5, "min"),
        vol.Required(native_option_key("suppress_notifications_at_night"), default=bool(current.get("suppress_notifications_at_night", False))): bool,
        vol.Optional("test_notification_now", default=False): bool,
    })


class FreshAirIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 8

    def __init__(self) -> None:
        self._base: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN); self._abort_if_unique_id_configured()
        legacy_entries = self.hass.config_entries.async_entries(LEGACY_DOMAIN)
        if legacy_entries and user_input is None:
            return await self.async_step_legacy_import()
        errors = {}
        if user_input is not None:
            error = _outdoor_configuration_error(dict(user_input))
            if error:
                errors["base"] = error
            else:
                self._base = {k: v for k, v in dict(user_input).items() if v not in (None, "")}
                # v0.24.14.0: installation is intentionally frictionless. Rooms,
                # outdoor sources and every advanced setting can be completed later
                # from Devices & Services or the dashboard gear.
                self._base.setdefault(CONF_ROOMS, [])
                self._base.setdefault(CONF_LEVELS, [])
                return self.async_create_entry(title="FreshAirIQ", data=self._base)
        return self.async_show_form(step_id="user", data_schema=_outdoor_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Reconfigure the mandatory outdoor data source.

        These values are setup data, not preferences, so expose the native HA
        reconfigure flow in addition to the broader FreshAirIQ options UI.
        """
        entry = self._get_reconfigure_entry()
        current = dict(entry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            error = _outdoor_configuration_error(dict(user_input))
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_mismatch()
                updates = {
                    key: (user_input.get(key) or None)
                    for key in (
                        CONF_OUTDOOR_WEATHER,
                        CONF_OUTDOOR_TEMPERATURE,
                        CONF_OUTDOOR_HUMIDITY,
                        CONF_POLLEN_ENTITY,
                    )
                }
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=updates,
                    reason="reconfigure_successful",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_outdoor_schema(current),
            errors=errors,
        )

    async def async_step_legacy_import(self, user_input=None) -> FlowResult:
        legacy_entries = self.hass.config_entries.async_entries(LEGACY_DOMAIN)
        if not legacy_entries:
            return await self.async_step_user(user_input={})
        legacy = legacy_entries[0]
        if user_input is not None:
            if user_input.get("import_legacy", True):
                data = _normalise_legacy_entry_data(dict(legacy.data)); data[CONF_LEGACY_ENTRY_ID] = legacy.entry_id
                data[CONF_LEVELS] = list(dict.fromkeys(r.get(CONF_ROOM_FLOOR, "Unzugeordnet") for r in data.get(CONF_ROOMS, [])))
                subentries = [
                    {"subentry_type": "room", "data": dict(room), "title": room.get(CONF_ROOM_NAME, room["key"]), "unique_id": f"room:{room['key']}"}
                    for room in data.get(CONF_ROOMS, [])
                ]
                return self.async_create_entry(title="FreshAirIQ", data=data, subentries=subentries)
            return self.async_show_form(step_id="user", data_schema=_outdoor_schema())
        return self.async_show_form(step_id="legacy_import", data_schema=vol.Schema({vol.Required("import_legacy", default=True): bool}))

    async def async_step_room(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            room, errors = _normalise_room(user_input, self._rooms)
            if room and not errors:
                self._rooms.append(room); self._pending_room_key = room["key"]; return await self.async_step_room_orientations()
        return self.async_show_form(step_id="room", data_schema=_room_schema(levels=list(dict.fromkeys(r.get(CONF_ROOM_FLOOR, "") for r in self._rooms if r.get(CONF_ROOM_FLOOR)))), errors=errors, description_placeholders={"room_count": str(len(self._rooms) + 1)})

    async def async_step_room_orientations(self, user_input=None) -> FlowResult:
        room = next((r for r in self._rooms if r.get("key") == getattr(self, "_pending_room_key", None)), None)
        if room is None or not room.get(CONF_ROOM_CONTACTS):
            return await self.async_step_more_rooms()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {c: str(user_input.get(c, ORIENTATION_UNKNOWN)) for c in contacts}
            return await self.async_step_room_references()
        return self.async_show_form(step_id="room_orientations", data_schema=vol.Schema({
            vol.Required(c, default=str((room.get(CONF_CONTACT_ORIENTATIONS) or {}).get(c, ORIENTATION_UNKNOWN))): selector.SelectSelector(
                selector.SelectSelectorConfig(options=ORIENTATIONS, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="window_orientation")
            ) for c in contacts
        }), description_placeholders={"room_name": room.get("name", room["key"])})

    async def async_step_room_references(self, user_input=None) -> FlowResult:
        room = next((r for r in self._rooms if r.get("key") == getattr(self, "_pending_room_key", None)), None)
        contacts = list(room.get(CONF_ROOM_CONTACTS, []) or []) if room is not None else []
        if room is None or not contacts:
            self._room_reference_contact_index = 0
            return await self.async_step_more_rooms()
        index = int(getattr(self, "_room_reference_contact_index", 0) or 0)
        if index >= len(contacts):
            self._room_reference_contact_index = 0
            return await self.async_step_more_rooms()
        contact = str(contacts[index])
        errors = {}
        if user_input is not None:
            if _apply_single_contact_reference(room, contact, user_input):
                self._room_reference_contact_index = index + 1
                return await self.async_step_room_references()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="room_references",
            data_schema=_single_contact_reference_schema(room, contact),
            errors=errors,
            description_placeholders={
                "room_name": room.get(CONF_ROOM_NAME, room.get("key", _txt(_flow_language(self.hass), "Raum", "Room"))),
                "contact_name": _contact_display_name(self.hass, contact),
                "contact_entity": contact,
                "contact_position": str(index + 1),
                "contact_count": str(len(contacts)),
            },
        )

    async def async_step_more_rooms(self, user_input=None) -> FlowResult:
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_room()
            data = {**self._base, CONF_ROOMS: self._rooms, CONF_LEVELS: list(dict.fromkeys(r.get(CONF_ROOM_FLOOR, "Unzugeordnet") for r in self._rooms))}
            subentries = [
                {
                    "subentry_type": "room",
                    "data": dict(room),
                    "title": room.get(CONF_ROOM_NAME, room["key"]),
                    "unique_id": f"room:{room['key']}",
                }
                for room in self._rooms
            ]
            return self.async_create_entry(title="FreshAirIQ", data=data, subentries=subentries)
        return self.async_show_form(step_id="more_rooms", data_schema=vol.Schema({vol.Required("add_another", default=True): bool}), description_placeholders={"room_count": str(len(self._rooms))})

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: config_entries.ConfigEntry):
        """Expose rooms as native Home Assistant config subentries."""
        return {"room": FreshAirIQRoomSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return FreshAirIQOptionsFlow()


class FreshAirIQRoomSubentryFlow(config_entries.ConfigSubentryFlow):
    """Native Home Assistant editor for one FreshAirIQ room.

    Rooms are modelled as native Home Assistant subentries for identity/entity
    grouping and for the quick add-room flow. Existing room subentries are
    intentionally not reconfigurable: all FreshAirIQ settings are edited from
    the parent integration's central OptionsFlow.
    """

    def __init__(self) -> None:
        self._working_room: dict[str, Any] | None = None
        self._room_key: str | None = None

    def _entry_rooms(self) -> list[dict[str, Any]]:
        return [dict(room) for room in self._get_entry().data.get(CONF_ROOMS, [])]

    def _levels(self) -> list[str]:
        return list(self._get_entry().data.get(CONF_LEVELS, []))

    def _current_room(self) -> dict[str, Any]:
        if self._working_room is not None:
            return self._working_room
        subentry = self._get_reconfigure_subentry()
        key = (subentry.unique_id or "").removeprefix("room:") or str(subentry.data.get("key", ""))
        current = next((room for room in self._entry_rooms() if room.get("key") == key), dict(subentry.data))
        self._room_key = key
        self._working_room = dict(current)
        return self._working_room

    async def async_step_user(self, user_input=None):
        """Quick setup: choose manual room creation or Home Assistant import."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["create_room", "import_ha_room"],
        )

    async def async_step_create_room(self, user_input=None):
        """Create one room manually from the quick setup entry point."""
        rooms = self._entry_rooms()
        levels = self._levels()
        errors = {}
        if user_input is not None:
            trace_room_creation(self.hass, self._get_entry(), source="native_subentry", stage="attempt")
            room, errors = _normalise_room(user_input, rooms)
            if room and not errors:
                self._working_room = room
                self._room_key = room["key"]
                self._room_origin = "create_room"
                self._add_reference_contact_index = 0
                trace_room_creation(self.hass, self._get_entry(), source="native_subentry", stage="normalised", room_key=room["key"], outcome="ok")
                return await self.async_step_add_goals()
            trace_room_creation(self.hass, self._get_entry(), source="native_subentry", stage="validation_failed", outcome="rejected", extra={"validation_error_keys": sorted(map(str, errors))})
        # Coming back from the next page keeps what was already entered.
        return self.async_show_form(step_id="create_room", data_schema=_room_section_schema(self._working_room, levels=levels), errors=errors)

    def _quick_ha_area_defaults(self) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
        """Build safe HA-area import suggestions for the add-only quick flow."""
        area_reg = ar.async_get(self.hass)
        floor_reg = fr.async_get(self.hass)
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        existing_names = {str(room.get(CONF_ROOM_NAME, "")).strip().casefold() for room in self._entry_rooms()}
        choices: list[dict[str, str]] = []
        defaults: dict[str, dict[str, Any]] = {}
        for area in sorted(area_reg.async_list_areas(), key=lambda item: item.name.casefold()):
            if area.name.strip().casefold() in existing_names:
                continue
            unassigned = _txt(_flow_language(self.hass), "Unzugeordnet", "Unassigned")
            floor_name = unassigned
            if area.floor_id:
                floor = floor_reg.async_get_floor(area.floor_id)
                if floor is not None and floor.name:
                    floor_name = floor.name
            label = f"{floor_name} · {area.name}" if floor_name != unassigned else area.name
            candidates = {
                CONF_ROOM_TEMPERATURE: [], CONF_ROOM_HUMIDITY: [], CONF_ROOM_CONTACTS: [],
                CONF_ROOM_CO2: [], CONF_ROOM_ILLUMINANCE: [], CONF_ROOM_CLIMATE: [],
            }
            for entity_entry in entity_reg.entities.values():
                if entity_entry.disabled_by is not None:
                    continue
                entity_area_id = entity_entry.area_id
                if entity_area_id is None and entity_entry.device_id:
                    device = device_reg.async_get(entity_entry.device_id)
                    if device is not None:
                        entity_area_id = dr.async_get_effective_area_id(self.hass, device)
                if entity_area_id != area.id:
                    continue
                entity_id = entity_entry.entity_id
                domain = entity_id.split(".", 1)[0]
                state = self.hass.states.get(entity_id)
                device_class = getattr(entity_entry, "device_class", None)
                if state is not None:
                    device_class = state.attributes.get("device_class") or device_class
                device_class = str(getattr(device_class, "value", device_class) or "")
                if domain == "sensor":
                    if device_class == "temperature": candidates[CONF_ROOM_TEMPERATURE].append(entity_id)
                    elif device_class == "humidity": candidates[CONF_ROOM_HUMIDITY].append(entity_id)
                    elif device_class == "carbon_dioxide": candidates[CONF_ROOM_CO2].append(entity_id)
                    elif device_class == "illuminance": candidates[CONF_ROOM_ILLUMINANCE].append(entity_id)
                elif domain == "binary_sensor" and device_class in {"door", "garage_door", "opening", "window"}:
                    candidates[CONF_ROOM_CONTACTS].append(entity_id)
                elif domain == "climate":
                    candidates[CONF_ROOM_CLIMATE].append(entity_id)
            suggested: dict[str, Any] = {CONF_ROOM_NAME: area.name, CONF_ROOM_FLOOR: floor_name}
            preferred = {
                CONF_ROOM_TEMPERATURE: getattr(area, "temperature_entity_id", None),
                CONF_ROOM_HUMIDITY: getattr(area, "humidity_entity_id", None),
            }
            for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):
                values = sorted(dict.fromkeys(candidates[key]))
                preferred_id = preferred.get(key)
                if preferred_id and self.hass.states.get(preferred_id) is not None and preferred_id not in values:
                    values.insert(0, preferred_id)
                if values: suggested[key] = values
            for key in (CONF_ROOM_CO2, CONF_ROOM_ILLUMINANCE, CONF_ROOM_CLIMATE):
                values = sorted(dict.fromkeys(candidates[key]))
                if len(values) == 1: suggested[key] = values[0]
            contacts = sorted(dict.fromkeys(candidates[CONF_ROOM_CONTACTS]))
            if contacts: suggested[CONF_ROOM_CONTACTS] = contacts
            choices.append({"value": area.id, "label": label})
            defaults[area.id] = suggested
        return choices, defaults

    async def async_step_import_ha_room(self, user_input=None):
        """Choose one HA area to import through the quick setup entry point."""
        choices, defaults = self._quick_ha_area_defaults()
        if not choices:
            return self.async_show_form(step_id="import_ha_room", data_schema=vol.Schema({}), errors={"base": "no_ha_areas_to_import"})
        if user_input is not None:
            area_id = str(user_input.get("area") or "")
            if area_id in defaults:
                self._quick_import_defaults = defaults[area_id]
                return await self.async_step_import_ha_room_details()
        return self.async_show_form(
            step_id="import_ha_room",
            data_schema=vol.Schema({vol.Required("area"): selector.SelectSelector(selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN))}),
            errors={} if user_input is None else {"base": "select_ha_area"},
        )

    async def async_step_import_ha_room_details(self, user_input=None):
        """Complete one imported HA room, then use the canonical room wizard."""
        defaults = dict(getattr(self, "_quick_import_defaults", {}) or {})
        if not defaults:
            return await self.async_step_import_ha_room()
        errors = {}
        if user_input is not None:
            room, errors = _normalise_room(user_input, self._entry_rooms())
            if room and not errors:
                self._working_room = room
                self._room_key = room["key"]
                self._room_origin = "import_ha_room_details"
                self._add_reference_contact_index = 0
                trace_room_creation(self.hass, self._get_entry(), source="native_subentry_ha_import", stage="normalised", room_key=room["key"], outcome="ok")
                return await self.async_step_add_goals()
        suggested = {**defaults, CONF_ROOM_INCLUDE_CALCULATIONS: False}
        if user_input is None and self._working_room is not None:
            suggested.update(self._working_room)
        if user_input is not None:
            suggested.update(user_input)
        levels = list(dict.fromkeys([*self._levels(), str(defaults.get(CONF_ROOM_FLOOR) or _txt(_flow_language(self.hass), "Unzugeordnet", "Unassigned"))]))
        return self.async_show_form(
            step_id="import_ha_room_details",
            data_schema=_room_section_schema(suggested, levels=levels),
            errors=errors,
            description_placeholders={"room_name": str(defaults.get(CONF_ROOM_NAME) or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def _async_step_room_origin(self):
        """Back to the first page of the add-room wizard (manual or HA import)."""
        if getattr(self, "_room_origin", "create_room") == "import_ha_room_details":
            return await self.async_step_import_ha_room_details()
        return await self.async_step_create_room()

    async def async_step_add_goals(self, user_input=None):
        room = self._working_room or {}
        available = _available_room_goals(room)
        if len(available) <= 1:
            room[CONF_ROOM_GOAL_PRIORITIES] = list(available)
            return await self.async_step_add_references()
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self._async_step_room_origin()
            errors = _goal_priority_errors(user_input, room)
            if not errors:
                room[CONF_ROOM_GOAL_PRIORITIES] = _ranked_goal_priorities(user_input, room)
                self._add_reference_contact_index = 0
                return await self.async_step_add_references()
        return self.async_show_form(step_id="add_goals", data_schema=_goal_priority_schema(room, include_back=True), errors=errors)

    # 0.26.4.4: the separate "orientation" and "delay" pages were removed from the
    # add-room wizard; the per-opening page below already asks for both.

    async def async_step_add_references(self, user_input=None):
        """Configure each opening reference, then atomically create the room subentry."""
        room = self._working_room or {}
        contacts = list(room.get(CONF_ROOM_CONTACTS, []) or [])
        index = int(getattr(self, "_add_reference_contact_index", 0) or 0)

        # No contact is a supported room configuration. In that case there is
        # no per-opening page and creation proceeds directly to the same atomic
        # finalizer used after the last configured contact.
        if contacts and index < len(contacts):
            contact = str(contacts[index])
            errors = {}
            if user_input is not None:
                if bool(user_input.get("wizard_back")):
                    if index > 0:
                        self._add_reference_contact_index = index - 1
                        return await self.async_step_add_references()
                    if len(_available_room_goals(room)) > 1:
                        return await self.async_step_add_goals()
                    return await self._async_step_room_origin()
                if _apply_single_contact_reference(room, contact, user_input):
                    self._add_reference_contact_index = index + 1
                    return await self.async_step_add_references()
                errors["base"] = "contact_reference_pair_required"
            return self.async_show_form(
                step_id="add_references",
                data_schema=_schema_with_wizard_back(_single_contact_reference_schema(room, contact)),
                errors=errors,
                description_placeholders={
                    "room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room")),
                    "contact_name": _contact_display_name(self.hass, contact),
                    "contact_entity": contact,
                    "contact_position": str(index + 1),
                    "contact_count": str(len(contacts)),
                },
            )

        self._add_reference_contact_index = 0
        entry = self._get_entry()
        room_to_commit = dict(room)
        unique_id = f"room:{room_to_commit['key']}"

        async def _commit_parent_after_subentry() -> None:
            # The ConfigSubentryFlowManager owns the actual subentry commit.
            # Never publish the room into canonical parent data before that
            # commit has completed: async_setup_entry() mirrors parent rooms
            # back into subentries, so parent-first persistence can race or
            # leave a ghost room when the HA flow itself fails.
            # Home Assistant commits CREATE_ENTRY in
            # ConfigSubentryFlowManager.async_finish_flow(), after this flow
            # step has returned.  A single sleep(0) is not a commit barrier:
            # on a busy installation our task may resume before HA has added
            # the subentry.  Wait for the observable HA commit for a short,
            # bounded period instead of treating the first scheduler turn as
            # definitive.
            committed = None
            await asyncio.sleep(0)
            for _attempt in range(20):
                await asyncio.sleep(0.05)
                committed = next(
                    (
                        subentry
                        for subentry in entry.subentries.values()
                        if subentry.subentry_type == "room"
                        and subentry.unique_id == unique_id
                    ),
                    None,
                )
                if committed is not None:
                    break
            if committed is None:
                # No successful HA subentry commit means no canonical room
                # mutation and no reload. This keeps a failed flow atomic.
                trace_room_creation(self.hass, entry, source="native_subentry", stage="subentry_commit_timeout", room_key=room_to_commit["key"], outcome="missing", extra={"commit_wait_ms": 1000})
                return

            trace_room_creation(self.hass, entry, source="native_subentry", stage="subentry_commit_observed", room_key=room_to_commit["key"], outcome="ok")
            rooms = [dict(existing) for existing in entry.data.get(CONF_ROOMS, [])]
            if not any(existing.get("key") == room_to_commit["key"] for existing in rooms):
                rooms.append(room_to_commit)
            data = dict(entry.data)
            data[CONF_ROOMS] = rooms
            levels = list(data.get(CONF_LEVELS, []))
            floor = room_to_commit.get(CONF_ROOM_FLOOR)
            if floor and floor not in levels:
                levels.append(floor)
            data[CONF_LEVELS] = levels
            self.hass.config_entries.async_update_entry(entry, data=data)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            trace_room_creation(self.hass, entry, source="native_subentry", stage="parent_persisted", room_key=room_to_commit["key"], outcome="ok", extra={"reload_scheduled": True})
            trace_room_creation_after_reload(self.hass, entry.entry_id, source="native_subentry", room_key=room_to_commit["key"])

        # Start the post-commit synchronizer now. hass.async_create_task()
        # runs eagerly until its first await; the explicit sleep above yields
        # back to Home Assistant so ConfigSubentryFlowManager.async_finish_flow
        # can commit the CREATE_ENTRY result first.
        self.hass.async_create_task(_commit_parent_after_subentry())
        return self.async_create_entry(
            title=room_to_commit.get(CONF_ROOM_NAME, room_to_commit["key"]),
            data=room_to_commit,
            unique_id=unique_id,
        )

    def _schedule_room_runtime_update(self) -> None:
        """Apply an existing-room edit without unloading FreshAirIQ entities."""
        coordinator = getattr(self._get_entry(), "runtime_data", None)
        if coordinator is None:
            return

        async def _apply() -> None:
            await coordinator.async_rebuild_listeners()
            await coordinator.async_request_refresh()

        self.hass.async_create_task(_apply())

    def _persist_room_update(self) -> None:
        """Persist the currently edited room immediately after a submitted page."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        room = dict(self._current_room())
        rooms = self._entry_rooms()
        replaced = False
        for idx, existing in enumerate(rooms):
            if existing.get("key") == self._room_key:
                rooms[idx] = dict(room)
                replaced = True
                break
        if not replaced:
            rooms.append(dict(room))
        data = dict(entry.data)
        data[CONF_ROOMS] = rooms
        levels = list(data.get(CONF_LEVELS, []))
        floor = room.get(CONF_ROOM_FLOOR)
        if floor and floor not in levels:
            levels.append(floor)
        data[CONF_LEVELS] = levels
        self.hass.config_entries.async_update_entry(entry, data=data)
        self.hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=dict(room),
            title=room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room")),
        )
        self._schedule_room_runtime_update()

    async def _async_step_reconfigure_legacy(self, user_input=None):
        """Open a clear room-local settings menu."""
        self._current_room()
        room = self._current_room()
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["room_basics", "room_goals", "room_references", "save_room"],
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def async_step_room_basics(self, user_input=None):
        room = self._current_room()
        rooms = self._entry_rooms()
        errors = {}
        if user_input is not None:
            updated, errors = _normalise_room(user_input, rooms, keep_key=self._room_key)
            if updated and not errors:
                # Preserve contact-specific values for contacts that still exist.
                contacts = set(updated.get(CONF_ROOM_CONTACTS, []))
                updated[CONF_CONTACT_ORIENTATIONS] = {
                    k: v for k, v in (room.get(CONF_CONTACT_ORIENTATIONS) or {}).items() if k in contacts
                }
                updated[CONF_CONTACT_DELAYS] = {
                    k: v for k, v in (room.get(CONF_CONTACT_DELAYS) or {}).items() if k in contacts
                }
                self._working_room = updated
                self._persist_room_update()
                return await self._async_step_reconfigure_legacy()
        return self.async_show_form(
            step_id="room_basics",
            data_schema=_room_section_schema(room, self._levels()),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def async_step_room_goals(self, user_input=None):
        room = self._current_room()
        available = _available_room_goals(room)
        if len(available) <= 1:
            room[CONF_ROOM_GOAL_PRIORITIES] = list(available)
            self._persist_room_update()
            return await self._async_step_reconfigure_legacy()
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self._async_step_reconfigure_legacy()
            errors = _goal_priority_errors(user_input, room)
            if not errors:
                room[CONF_ROOM_GOAL_PRIORITIES] = _ranked_goal_priorities(user_input, room)
                self._persist_room_update()
                return await self._async_step_reconfigure_legacy()
        return self.async_show_form(
            step_id="room_goals", data_schema=_goal_priority_schema(room, include_back=True), errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def async_step_room_orientations(self, user_input=None):
        room = self._current_room()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self._async_step_reconfigure_legacy()
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {
                contact: str(user_input.get(contact, ORIENTATION_UNKNOWN)) for contact in contacts
            }
            self._persist_room_update()
            return await self._async_step_reconfigure_legacy()
        current = room.get(CONF_CONTACT_ORIENTATIONS, {})
        fallback = room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)
        return self.async_show_form(
            step_id="room_orientations",
            data_schema=vol.Schema({
                vol.Required(contact, default=str(current.get(contact, fallback))): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ORIENTATIONS, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="window_orientation")
                ) for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def async_step_room_delays(self, user_input=None):
        room = self._current_room()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self._async_step_reconfigure_legacy()
        if user_input is not None:
            room[CONF_CONTACT_DELAYS] = {contact: _safe_int(user_input.get(contact, 0), 0, minimum=0, maximum=600) for contact in contacts}
            self._persist_room_update()
            return await self._async_step_reconfigure_legacy()
        current = room.get(CONF_CONTACT_DELAYS, {})
        return self.async_show_form(
            step_id="room_delays",
            data_schema=vol.Schema({
                vol.Optional(contact, default=_safe_int(current.get(contact, room.get(CONF_CONTACT_DELAY, 0)), 0, minimum=0, maximum=600)): _number(0, 600, 1, "s")
                for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room"))},
        )

    async def async_step_room_references(self, user_input=None):
        room = self._current_room()
        contacts = list(room.get(CONF_ROOM_CONTACTS, []) or [])
        if not contacts:
            self._room_reference_contact_index = 0
            return await self._async_step_reconfigure_legacy()
        index = int(getattr(self, "_room_reference_contact_index", 0) or 0)
        if index >= len(contacts):
            self._room_reference_contact_index = 0
            self._persist_room_update()
            return await self._async_step_reconfigure_legacy()
        contact = str(contacts[index])
        errors = {}
        if user_input is not None:
            if _apply_single_contact_reference(room, contact, user_input):
                self._persist_room_update()
                self._room_reference_contact_index = index + 1
                return await self.async_step_room_references()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="room_references",
            data_schema=_single_contact_reference_schema(room, contact),
            errors=errors,
            description_placeholders={
                "room_name": room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room")),
                "contact_name": _contact_display_name(self.hass, contact),
                "contact_entity": contact,
                "contact_position": str(index + 1),
                "contact_count": str(len(contacts)),
            },
        )

    async def async_step_save_room(self, user_input=None):
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        room = self._current_room()
        rooms = self._entry_rooms()
        replaced = False
        for idx, existing in enumerate(rooms):
            if existing.get("key") == self._room_key:
                rooms[idx] = dict(room)
                replaced = True
                break
        if not replaced:
            rooms.append(dict(room))
        data = dict(entry.data)
        data[CONF_ROOMS] = rooms
        levels = list(data.get(CONF_LEVELS, []))
        floor = room.get(CONF_ROOM_FLOOR)
        if floor and floor not in levels:
            levels.append(floor)
        data[CONF_LEVELS] = levels
        self.hass.config_entries.async_update_entry(entry, data=data)
        self._schedule_room_runtime_update()
        # Native subentry helper keeps Home Assistant's subentry state in sync.
        return self.async_update_and_abort(
            entry,
            subentry,
            data=dict(room),
            title=room.get(CONF_ROOM_NAME, self._room_key or _txt(_flow_language(self.hass), "Raum", "Room")),
        )


class FreshAirIQOptionsFlow(config_entries.OptionsFlowWithReload):
    def __init__(self) -> None:
        self._working_data = None; self._working_options = None; self._selected_room_key = None
        self._ha_import_queue: list[dict[str, str]] = []

    def _ensure_working_copy(self) -> None:
        if self._working_data is None:
            self._working_data = _normalise_legacy_entry_data(dict(self.config_entry.data))
        if self._working_options is None:
            self._working_options = {**DEFAULT_OPTIONS, **dict(self.config_entry.options)}

    def _rooms(self) -> list[dict[str, Any]]:
        self._ensure_working_copy()
        rooms = self._working_data.setdefault(CONF_ROOMS, [])
        rooms.sort(key=lambda r: (_safe_int(r.get(CONF_ROOM_SORT_ORDER), 9999, minimum=0), r.get("name", "")))
        for idx, room in enumerate(rooms): room[CONF_ROOM_SORT_ORDER] = idx
        return rooms

    def _room_selector(self):
        return selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": r["key"], "label": r.get("name", r["key"])} for r in self._rooms()], mode=selector.SelectSelectorMode.DROPDOWN))

    def _persist_working_state(self, *, reload_entry: bool = True) -> bool:
        """Persist the current page immediately without closing the options flow.

        Home Assistant data-entry forms cannot save individual fields while the user is
        still typing.  The earliest reliable point is therefore the form submission.
        FreshAirIQ writes the submitted page to the config entry immediately, mirrors
        room subentries, and optionally reloads the integration.
        """
        self._ensure_working_copy()
        old_data = dict(self.config_entry.data)
        old_options = dict(self.config_entry.options)
        new_data = deepcopy(self._working_data)
        new_options = deepcopy(self._working_options)
        data_changed = new_data != old_data
        options_changed = new_options != old_options

        if data_changed or options_changed:
            kwargs = {}
            if data_changed:
                kwargs["data"] = new_data
            if options_changed:
                kwargs["options"] = new_options
            self.hass.config_entries.async_update_entry(self.config_entry, **kwargs)

        if data_changed:
            # Keep native room subentries in lockstep with the canonical room data.
            by_unique = {
                sub.unique_id: sub
                for sub in self.config_entry.subentries.values()
                if sub.subentry_type == "room"
            }
            room_keys = {room["key"] for room in new_data.get(CONF_ROOMS, [])}
            for unique_id, subentry in list(by_unique.items()):
                key = (unique_id or "").removeprefix("room:")
                if key not in room_keys:
                    self.hass.config_entries.async_remove_subentry(
                        self.config_entry, subentry.subentry_id
                    )
            for room in new_data.get(CONF_ROOMS, []):
                unique_id = f"room:{room['key']}"
                existing = by_unique.get(unique_id)
                if existing is not None:
                    self.hass.config_entries.async_update_subentry(
                        self.config_entry,
                        existing,
                        data=dict(room),
                        title=room.get(CONF_ROOM_NAME, room["key"]),
                    )
                else:
                    from types import MappingProxyType

                    self.hass.config_entries.async_add_subentry(
                        self.config_entry,
                        config_entries.ConfigSubentry(
                            data=MappingProxyType(dict(room)),
                            subentry_type="room",
                            title=room.get(CONF_ROOM_NAME, room["key"]),
                            unique_id=unique_id,
                        ),
                    )

        changed = data_changed or options_changed
        if changed and reload_entry:
            changed_data_keys = {
                key for key in set(old_data) | set(new_data)
                if old_data.get(key) != new_data.get(key)
            }
            changed_option_keys = {
                key for key in set(old_options) | set(new_options)
                if old_options.get(key) != new_options.get(key)
            }
            # Room structure changes still need a real config-entry reload because
            # HA platform entities are created per room during async_setup_entry.
            # All other settings are consumed live by the coordinator and can be
            # applied without tearing down/recreating the complete integration.
            old_room_keys = {str(room.get("key")) for room in old_data.get(CONF_ROOMS, [])}
            new_room_keys = {str(room.get("key")) for room in new_data.get(CONF_ROOMS, [])}
            structural_change = old_room_keys != new_room_keys
            if structural_change:
                self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            else:
                coordinator = getattr(self.config_entry, "runtime_data", None)
                if coordinator is not None:
                    rebuild_listeners = bool(
                        changed_data_keys & _RUNTIME_LISTENER_DATA_KEYS
                        or changed_option_keys & _RUNTIME_LISTENER_OPTION_KEYS
                    )

                    invalidate_weather_cache = (
                        CONF_OUTDOOR_WEATHER in changed_data_keys
                    )

                    async def _apply_runtime_change() -> None:
                        if rebuild_listeners:
                            await coordinator.async_rebuild_listeners(
                                invalidate_weather_cache=invalidate_weather_cache
                            )
                        await coordinator.async_request_refresh()
                        if {"diagnostics_reporting_mode", "diagnostics_consent"} & set(changed_option_keys):
                            coordinator.telemetry.request_check()

                    self.hass.async_create_task(_apply_runtime_change())
        return changed

    def _commit_and_close(self) -> FlowResult:
        """Persist any remaining state and close the options dialog."""
        self._persist_working_state(reload_entry=True)
        return self.async_create_entry(data=deepcopy(self._working_options))

    async def async_step_init(self, user_input=None):
        # Dashboard and native options write the same ConfigEntry. Rebase the
        # native working copy whenever the main menu is entered so a dashboard
        # change made while an options dialog was open cannot remain stale or
        # later overwrite the newer value. In-progress submenu edits are already
        # persisted before returning here.
        self._working_data = _normalise_legacy_entry_data(dict(self.config_entry.data))
        self._working_options = {**DEFAULT_OPTIONS, **dict(self.config_entry.options)}
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "home_setup",
                "ventilation_settings",
                "notification_energy_settings",
                "data_learning_settings",
                "maintenance",
                "finish",
            ],
        )

    async def async_step_home_setup(self, user_input=None):
        return self.async_show_menu(
            step_id="home_setup",
            menu_options=["outdoor", "building", "residents", "levels", "rooms", "back_to_main"],
        )

    async def async_step_ventilation_settings(self, user_input=None):
        return self.async_show_menu(
            step_id="ventilation_settings",
            menu_options=[
                "profile",
                "forecast",
                "air_quality",
                "cross_ventilation",
                "recommendation_priorities",
                "threshold",
                "model",
                "back_to_main",
            ],
        )

    async def async_step_notification_energy_settings(self, user_input=None):
        return self.async_show_menu(
            step_id="notification_energy_settings",
            menu_options=["notifications", "energy", "back_to_main"],
        )

    async def async_step_data_learning_settings(self, user_input=None):
        return self.async_show_menu(
            step_id="data_learning_settings",
            menu_options=["statistics", "diagnostics_sharing", "back_to_main"],
        )

    # Compatibility aliases for flows started with v0.19.0.0 or older.
    async def async_step_comfort_health(self, user_input=None):
        return await self.async_step_ventilation_settings(user_input)

    async def async_step_automation_costs(self, user_input=None):
        return await self.async_step_notification_energy_settings(user_input)

    async def async_step_expert_data(self, user_input=None):
        return await self.async_step_data_learning_settings(user_input)

    async def async_step_maintenance(self, user_input=None):
        return self.async_show_menu(
            step_id="maintenance",
            menu_options=["reset_learning", "reset_defaults", "back_to_main"],
        )

    async def async_step_outdoor(self, user_input=None):
        self._ensure_working_copy()
        errors = {}
        if user_input is not None:
            error = _outdoor_configuration_error(dict(user_input))
            if error:
                errors["base"] = error
            else:
                for key in (
                    CONF_OUTDOOR_WEATHER,
                    CONF_OUTDOOR_TEMPERATURE,
                    CONF_OUTDOOR_HUMIDITY,
                    CONF_POLLEN_ENTITY,
                ):
                    value = user_input.get(key)
                    if value in (None, ""):
                        self._working_data.pop(key, None)
                    else:
                        self._working_data[key] = value
                self._persist_working_state()
                return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="outdoor",
            data_schema=_outdoor_schema(self._working_data),
            errors=errors,
        )

    async def async_step_rooms(self, user_input=None):
        # Canonical room administration. Native room subentries remain visible
        # for Home Assistant identity/entity grouping but are intentionally
        # add-only and expose no separate FreshAirIQ reconfigure flow.
        menu = ["add_room", "import_ha_rooms"]
        if self._rooms():
            menu.extend(["edit_room_select", "sort_rooms", "remove_room"])
        menu.append("back_to_home_setup")
        return self.async_show_menu(step_id="rooms", menu_options=menu)

    def _ha_area_entity_defaults(self, area_id: str) -> dict[str, Any]:
        """Return safe FreshAirIQ sensor suggestions for one Home Assistant area.

        Area assignment follows Home Assistant's registry semantics: an entity's
        explicit area wins, otherwise the effective device area is used.  The
        latter also handles child devices which inherit their parent's area.
        Suggestions are only defaults for newly imported rooms; they never
        overwrite an existing FreshAirIQ room or a later manual selection.
        """
        area_reg = ar.async_get(self.hass)
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        area = area_reg.async_get_area(area_id)
        if area is None:
            return {}

        candidates: dict[str, list[str]] = {
            CONF_ROOM_TEMPERATURE: [],
            CONF_ROOM_HUMIDITY: [],
            CONF_ROOM_CONTACTS: [],
            CONF_ROOM_CO2: [],
            CONF_ROOM_ILLUMINANCE: [],
            CONF_ROOM_CLIMATE: [],
        }

        for entity_entry in entity_reg.entities.values():
            if entity_entry.disabled_by is not None:
                continue
            entity_area_id = entity_entry.area_id
            if entity_area_id is None and entity_entry.device_id:
                device = device_reg.async_get(entity_entry.device_id)
                if device is not None:
                    entity_area_id = dr.async_get_effective_area_id(self.hass, device)
            if entity_area_id != area_id:
                continue

            entity_id = entity_entry.entity_id
            domain = entity_id.split(".", 1)[0]
            state = self.hass.states.get(entity_id)
            device_class = getattr(entity_entry, "device_class", None)
            if state is not None:
                device_class = state.attributes.get("device_class") or device_class
            device_class = str(getattr(device_class, "value", device_class) or "")

            if domain == "sensor":
                if device_class == "temperature":
                    candidates[CONF_ROOM_TEMPERATURE].append(entity_id)
                elif device_class == "humidity":
                    candidates[CONF_ROOM_HUMIDITY].append(entity_id)
                elif device_class == "carbon_dioxide":
                    candidates[CONF_ROOM_CO2].append(entity_id)
                elif device_class == "illuminance":
                    candidates[CONF_ROOM_ILLUMINANCE].append(entity_id)
            elif domain == "binary_sensor" and device_class in {
                "door", "garage_door", "opening", "window"
            }:
                candidates[CONF_ROOM_CONTACTS].append(entity_id)
            elif domain == "climate":
                candidates[CONF_ROOM_CLIMATE].append(entity_id)

        defaults: dict[str, Any] = {}
        # HA allows an area to designate its canonical temperature/humidity
        # entity. Prefer those over heuristic candidates when they are valid.
        preferred = {
            CONF_ROOM_TEMPERATURE: getattr(area, "temperature_entity_id", None),
            CONF_ROOM_HUMIDITY: getattr(area, "humidity_entity_id", None),
        }
        for key, entity_id in preferred.items():
            if entity_id and self.hass.states.get(entity_id) is not None:
                defaults[key] = entity_id

        for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY, CONF_ROOM_CO2, CONF_ROOM_ILLUMINANCE, CONF_ROOM_CLIMATE):
            values = sorted(dict.fromkeys(candidates[key]))
            if key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):
                # Multi-sensor climate is explicit: show the complete detected
                # redundant set during import so the user can confirm/remove it.
                preferred_id = preferred.get(key)
                if preferred_id and preferred_id not in values:
                    values.insert(0, preferred_id)
                if values:
                    defaults[key] = values
            elif key not in defaults and len(values) == 1:
                defaults[key] = values[0]
        contacts = sorted(dict.fromkeys(candidates[CONF_ROOM_CONTACTS]))
        if contacts:
            defaults[CONF_ROOM_CONTACTS] = contacts
        return defaults

    def _ha_area_options(self) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
        """Return HA areas as import choices plus their FreshAirIQ defaults."""
        area_reg = ar.async_get(self.hass)
        floor_reg = fr.async_get(self.hass)
        existing_names = {str(room.get(CONF_ROOM_NAME, "")).strip().casefold() for room in self._rooms()}
        choices: list[dict[str, str]] = []
        defaults: dict[str, dict[str, str]] = {}
        for area in sorted(area_reg.async_list_areas(), key=lambda item: item.name.casefold()):
            if area.name.strip().casefold() in existing_names:
                continue
            unassigned = _txt(_flow_language(self.hass), "Unzugeordnet", "Unassigned")
            floor_name = unassigned
            if area.floor_id:
                floor = floor_reg.async_get_floor(area.floor_id)
                if floor is not None and floor.name:
                    floor_name = floor.name
            label = f"{floor_name} · {area.name}" if floor_name != unassigned else area.name
            choices.append({"value": area.id, "label": label})
            defaults[area.id] = {
                CONF_ROOM_NAME: area.name,
                CONF_ROOM_FLOOR: floor_name,
                **self._ha_area_entity_defaults(area.id),
            }
        return choices, defaults

    async def async_step_import_ha_rooms(self, user_input=None):
        """Import HA floor/area structure and complete each room in FreshAirIQ."""
        choices, defaults = self._ha_area_options()
        if not choices:
            return self.async_show_form(
                step_id="import_ha_rooms",
                data_schema=vol.Schema({}),
                errors={"base": "no_ha_areas_to_import"},
            )
        if user_input is not None:
            selected = user_input.get("areas") or []
            if isinstance(selected, str):
                selected = [selected]
            self._ha_import_queue = [defaults[area_id] for area_id in selected if area_id in defaults]
            if not self._ha_import_queue:
                return self.async_show_form(
                    step_id="import_ha_rooms",
                    data_schema=vol.Schema({
                        vol.Required("areas"): selector.SelectSelector(
                            selector.SelectSelectorConfig(options=choices, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
                        )
                    }),
                    errors={"base": "select_ha_area"},
                )
            return await self.async_step_import_ha_room_details()
        return self.async_show_form(
            step_id="import_ha_rooms",
            data_schema=vol.Schema({
                vol.Required("areas"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }),
        )

    async def async_step_import_ha_room_details(self, user_input=None):
        """Complete required FreshAirIQ data for one imported HA area."""
        if not self._ha_import_queue:
            self._persist_working_state()
            return await self.async_step_rooms()
        imported = self._ha_import_queue[0]
        errors = {}
        if user_input is not None:
            room, errors = _normalise_room(user_input, self._rooms())
            if room and not errors:
                self._rooms().append(room)
                floor = room.get(CONF_ROOM_FLOOR)
                levels = self._working_data.setdefault(CONF_LEVELS, [])
                if floor and floor not in levels:
                    levels.append(floor)
                self._ha_import_queue.pop(0)
                self._persist_working_state()
                return await self.async_step_import_ha_room_details()
        defaults = {
            **imported,
            CONF_ROOM_NAME: imported[CONF_ROOM_NAME],
            CONF_ROOM_FLOOR: imported[CONF_ROOM_FLOOR],
            CONF_ROOM_INCLUDE_CALCULATIONS: False,
        }
        if user_input is not None:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="import_ha_room_details",
            data_schema=_room_section_schema(defaults, levels=list(dict.fromkeys([*self._working_data.get(CONF_LEVELS, []), imported[CONF_ROOM_FLOOR]]))),
            errors=errors,
            description_placeholders={
                "room_name": imported[CONF_ROOM_NAME],
                "remaining": str(len(self._ha_import_queue)),
            },
        )

    async def async_step_add_room(self, user_input=None):
        errors = {}
        if user_input is not None:
            trace_room_creation(self.hass, self.config_entry, source="options_flow", stage="attempt")
            room, errors = _normalise_room(user_input, self._rooms())
            if room and not errors:
                self._rooms().append(room)
                self._selected_room_key = room["key"]
                trace_room_creation(self.hass, self.config_entry, source="options_flow", stage="normalised", room_key=room["key"], outcome="ok")
                # Save the valid base room immediately. Direction/delay forms
                # enrich the same room on the next screens.
                # Keep the multi-step room wizard alive while orientation/delay/reference
                # metadata is collected. Scheduling a config-entry reload here can tear
                # down the options flow before the next form is submitted, which HA
                # surfaces as the generic "Unknown error occurred" dialog error.
                self._persist_working_state(reload_entry=False)
                trace_room_creation(self.hass, self.config_entry, source="options_flow", stage="parent_persisted", room_key=room["key"], outcome="ok", extra={"reload_scheduled": False})
                trace_room_creation_after_reload(self.hass, self.config_entry.entry_id, source="options_flow", room_key=room["key"])
                return await self.async_step_room_goals()
            trace_room_creation(self.hass, self.config_entry, source="options_flow", stage="validation_failed", outcome="rejected", extra={"validation_error_keys": sorted(map(str, errors))})
        return self.async_show_form(
            step_id="add_room",
            data_schema=_room_section_schema(
                levels=list(self._working_data.get(CONF_LEVELS, []))
            ),
            errors=errors,
        )

    async def async_step_room_goals(self, user_input=None):
        """Configure available ventilation goals in an explicit priority order."""
        room = next((r for r in self._rooms() if r.get("key") == self._selected_room_key), None)
        if room is None:
            return await self.async_step_rooms()
        available = _available_room_goals(room)
        if len(available) <= 1:
            room[CONF_ROOM_GOAL_PRIORITIES] = list(available)
            self._persist_working_state(reload_entry=False)
            return await self.async_step_contact_references()
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_edit_room()
            errors = _goal_priority_errors(user_input, room)
            if not errors:
                room[CONF_ROOM_GOAL_PRIORITIES] = _ranked_goal_priorities(user_input, room)
                self._persist_working_state(reload_entry=False)
                return await self.async_step_contact_references()
        return self.async_show_form(step_id="room_goals", data_schema=_goal_priority_schema(room, include_back=True), errors=errors)

    async def async_step_edit_room_select(self, user_input=None):
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_rooms()
            self._selected_room_key = user_input["room"]
            return await self.async_step_edit_room()
        return self.async_show_form(
            step_id="edit_room_select",
            data_schema=vol.Schema({
                vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
                vol.Required("room"): self._room_selector(),
            }),
        )

    async def async_step_edit_room(self, user_input=None):
        room = next(
            (r for r in self._rooms() if r["key"] == self._selected_room_key), None
        )
        if room is None:
            return await self.async_step_rooms()
        errors = {}
        if user_input is not None:
            updated, errors = _normalise_room(
                user_input, self._rooms(), keep_key=room["key"]
            )
            if updated and not errors:
                # Keep contact-specific metadata only for contacts that remain.
                contacts = set(updated.get(CONF_ROOM_CONTACTS, []))
                updated[CONF_CONTACT_ORIENTATIONS] = {
                    k: v
                    for k, v in (room.get(CONF_CONTACT_ORIENTATIONS) or {}).items()
                    if k in contacts
                }
                updated[CONF_CONTACT_DELAYS] = {
                    k: v
                    for k, v in (room.get(CONF_CONTACT_DELAYS) or {}).items()
                    if k in contacts
                }
                self._rooms()[self._rooms().index(room)] = updated
                self._selected_room_key = updated["key"]
                # Do not reload Home Assistant in the middle of the room wizard.
                # The final contact step (or the no-contact fast path) performs the
                # single structural reload after all room metadata is committed.
                self._persist_working_state(reload_entry=False)
                return await self.async_step_room_goals()
        return self.async_show_form(
            step_id="edit_room",
            data_schema=_room_section_schema(
                room, list(self._working_data.get(CONF_LEVELS, []))
            ),
            errors=errors,
            description_placeholders={"room_name": room.get("name", room["key"])},
        )

    async def async_step_sort_rooms(self, user_input=None):
        """Edit the complete room order on one page instead of one move per submit."""
        rooms = self._rooms()
        if not rooms:
            return await self.async_step_rooms()
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_rooms()
            ranked_keys = [
                str(user_input.get(f"room_position_{idx}") or "")
                for idx in range(1, len(rooms) + 1)
            ]
            current_keys = [str(room.get("key")) for room in rooms]
            if (
                len(ranked_keys) != len(current_keys)
                or set(ranked_keys) != set(current_keys)
                or len(set(ranked_keys)) != len(ranked_keys)
            ):
                return self.async_show_form(
                    step_id="sort_rooms",
                    data_schema=self._room_order_schema(rooms),
                    errors={"base": "invalid_room_order"},
                )
            by_key = {str(room.get("key")): room for room in rooms}
            rooms = [by_key[key] for key in ranked_keys]
            for idx, room in enumerate(rooms):
                room[CONF_ROOM_SORT_ORDER] = idx
            self._working_data[CONF_ROOMS] = rooms
            # Ordering is non-structural. Persist without a config-entry reload;
            # the options flow stays alive and returns to the room menu.
            self._persist_working_state(reload_entry=False)
            return await self.async_step_rooms()
        return self.async_show_form(
            step_id="sort_rooms",
            data_schema=self._room_order_schema(rooms),
        )

    def _room_order_schema(self, rooms: list[dict[str, Any]]) -> vol.Schema:
        options = [
            {"value": str(room["key"]), "label": str(room.get(CONF_ROOM_NAME, room["key"]))}
            for room in rooms
        ]
        fields: dict[Any, Any] = {
            vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
        }
        for idx, room in enumerate(rooms, start=1):
            fields[vol.Required(f"room_position_{idx}", default=str(room["key"]))] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        return vol.Schema(fields)

    async def async_step_contact_orientations_room(self, user_input=None):
        if user_input is not None:
            self._selected_room_key = user_input["room"]
            return await self.async_step_contact_references()
        return self.async_show_form(
            step_id="contact_orientations_room",
            data_schema=vol.Schema({vol.Required("room"): self._room_selector()}),
        )

    async def async_step_contact_orientations(self, user_input=None):
        room = next(
            (r for r in self._rooms() if r["key"] == self._selected_room_key), None
        )
        if room is None:
            return await self.async_step_rooms()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            # Contactless rooms are valid. This is the end of their room wizard,
            # so persist once with the structural reload that was deliberately
            # deferred while the wizard was active.
            self._persist_working_state(reload_entry=True)
            return await self.async_step_rooms()
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {
                c: str(user_input.get(c, ORIENTATION_UNKNOWN)) for c in contacts
            }
            self._persist_working_state(reload_entry=False)
            return await self.async_step_contact_delays()
        current = room.get(CONF_CONTACT_ORIENTATIONS, {})
        fallback = room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)
        return self.async_show_form(
            step_id="contact_orientations",
            data_schema=vol.Schema(
                {
                    vol.Required(c, default=str(current.get(c, fallback))): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=ORIENTATIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="window_orientation",
                        )
                    )
                    for c in contacts
                }
            ),
            description_placeholders={"room_name": room.get("name", room["key"])},
        )

    async def async_step_contact_delays_room(self, user_input=None):
        if user_input is not None:
            self._selected_room_key = user_input["room"]
            return await self.async_step_contact_delays()
        return self.async_show_form(
            step_id="contact_delays_room",
            data_schema=vol.Schema({vol.Required("room"): self._room_selector()}),
        )

    async def async_step_contact_delays(self, user_input=None):
        room = next(
            (r for r in self._rooms() if r["key"] == self._selected_room_key), None
        )
        if room is None:
            return await self.async_step_rooms()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self.async_step_rooms()
        if user_input is not None:
            room[CONF_CONTACT_DELAYS] = {
                c: _safe_int(user_input.get(c, 0), 0, minimum=0, maximum=600) for c in contacts
            }
            self._persist_working_state(reload_entry=False)
            return await self.async_step_contact_references()
        current = room.get(CONF_CONTACT_DELAYS, {})
        return self.async_show_form(
            step_id="contact_delays",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        c,
                        default=_safe_int(
                            current.get(c, room.get(CONF_CONTACT_DELAY, 0)),
                            0,
                            minimum=0,
                            maximum=600,
                        ),
                    ): _number(0, 600, 1, "s")
                    for c in contacts
                }
            ),
            description_placeholders={"room_name": room.get("name", room["key"])},
        )

    async def async_step_contact_references(self, user_input=None):
        room = next(
            (r for r in self._rooms() if r["key"] == self._selected_room_key), None
        )
        contacts = list(room.get(CONF_ROOM_CONTACTS, []) or []) if room is not None else []
        if room is None or not contacts:
            self._contact_reference_index = 0
            return await self.async_step_rooms()
        index = int(getattr(self, "_contact_reference_index", 0) or 0)
        if index >= len(contacts):
            self._contact_reference_index = 0
            self._persist_working_state(reload_entry=True)
            return await self.async_step_rooms()
        contact = str(contacts[index])
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                if index > 0:
                    self._contact_reference_index = index - 1
                    return await self.async_step_contact_references()
                return await self.async_step_room_goals()
            if _apply_single_contact_reference(room, contact, user_input):
                self._persist_working_state(reload_entry=False)
                self._contact_reference_index = index + 1
                return await self.async_step_contact_references()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="contact_references",
            data_schema=_schema_with_wizard_back(_single_contact_reference_schema(room, contact)),
            errors=errors,
            description_placeholders={
                "room_name": room.get(CONF_ROOM_NAME, room.get("key", _txt(_flow_language(self.hass), "Raum", "Room"))),
                "contact_name": _contact_display_name(self.hass, contact),
                "contact_entity": contact,
                "contact_position": str(index + 1),
                "contact_count": str(len(contacts)),
            },
        )

    async def async_step_remove_room(self, user_input=None):
        if user_input is not None:
            if user_input.get("confirm"):
                key = user_input["room"]
                self._working_data[CONF_ROOMS] = [
                    r for r in self._rooms() if r["key"] != key
                ]
                self._persist_working_state()
            return await self.async_step_rooms()
        return self.async_show_form(
            step_id="remove_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room"): self._room_selector(),
                    vol.Required("confirm", default=False): bool,
                }
            ),
        )

    async def async_step_levels(self, user_input=None):
        self._ensure_working_copy()
        levels = list(self._working_data.get(CONF_LEVELS, []))
        for room in self._rooms():
            label = str(room.get(CONF_ROOM_FLOOR, "")).strip()
            if label and label not in levels:
                levels.append(label)
        self._working_data[CONF_LEVELS] = levels
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_level_add()
            if action == "reorder":
                return await self.async_step_level_reorder()
            if action == "remove":
                return await self.async_step_level_remove()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="levels",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["add", "reorder", "remove", "back"],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="level_action",
                        )
                    )
                }
            ),
            description_placeholders={
                "levels": ", ".join(_level_label(x, _flow_language(self.hass)) for x in levels)
                if levels
                else _txt(_flow_language(self.hass), "Noch keine Bereiche", "No areas yet")
            },
        )

    async def async_step_level_add(self, user_input=None):
        if user_input is not None:
            name = str(user_input.get("name", "")).strip()
            levels = self._working_data.setdefault(CONF_LEVELS, [])
            if name and name not in levels:
                levels.append(name)
                self._persist_working_state()
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_add",
            data_schema=vol.Schema({vol.Required("name"): selector.TextSelector()}),
        )

    async def async_step_level_reorder(self, user_input=None):
        levels = list(self._working_data.get(CONF_LEVELS, []))
        # Home Assistant renders dynamic schema keys literally. Localized labels
        # therefore become the form keys, while stored level ids stay unchanged.
        if user_input is not None:
            indexed = {level: i for i, level in enumerate(levels)}
            ordered = sorted(
                levels,
                key=lambda level: (
                    int(user_input.get(_level_label(level, _flow_language(self.hass)), indexed[level] + 1)),
                    indexed[level],
                ),
            )
            self._working_data[CONF_LEVELS] = ordered
            self._persist_working_state()
            return await self.async_step_levels()
        fields = {
            vol.Required(_level_label(level, _flow_language(self.hass)), default=idx): _number(
                1, max(len(levels), 1), 1
            )
            for idx, level in enumerate(levels, start=1)
        }
        if not fields:
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_reorder",
            data_schema=vol.Schema(fields),
        )

    async def async_step_level_remove(self, user_input=None):
        levels = list(self._working_data.get(CONF_LEVELS, []))
        used = {str(r.get(CONF_ROOM_FLOOR, "")) for r in self._rooms()}
        removable = [x for x in levels if x not in used]
        if user_input is not None:
            name = user_input.get("name")
            self._working_data[CONF_LEVELS] = [x for x in levels if x != name]
            self._persist_working_state()
            return await self.async_step_levels()
        opts = [{"value": x, "label": _level_label(x, _flow_language(self.hass))} for x in removable]
        if not opts:
            return await self.async_step_levels()
        return self.async_show_form(
            step_id="level_remove",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=opts, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )


    async def async_step_threshold(self, user_input=None):
        """Configure the house-wide ventilation threshold without ambiguous fields."""
        self._ensure_working_copy()
        if user_input is not None:
            mode = _choice(user_input.get("threshold_mode"), "adaptive_home_size", ["adaptive_home_size", "percent_total_water", "fixed_ml"])
            self._working_options["threshold_mode"] = mode
            self._persist_working_state()
            if mode == "percent_total_water":
                return await self.async_step_threshold_percent()
            if mode == "fixed_ml":
                return await self.async_step_threshold_fixed()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold",
            data_schema=vol.Schema({
                vol.Required(native_option_key("threshold_mode"), default=_choice(self._working_options.get("threshold_mode"), "adaptive_home_size", ["adaptive_home_size", "percent_total_water", "fixed_ml"])): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["adaptive_home_size", "percent_total_water", "fixed_ml"], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="threshold_mode")
                )
            }),
        )

    async def async_step_threshold_percent(self, user_input=None):
        """Configure only the percentage value for percentage mode."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["min_potential_percent_total_water"] = float(user_input["min_potential_percent_total_water"])
            self._working_options["threshold_mode"] = "percent_total_water"
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold_percent",
            data_schema=vol.Schema({
                vol.Required(native_option_key("min_potential_percent_total_water"), default=_bounded(self._working_options.get("min_potential_percent_total_water"), 10, 1, 30)): _number(1, 30, 0.5, "%")
            }),
        )

    async def async_step_threshold_fixed(self, user_input=None):
        """Configure only the fixed mL value for fixed mode."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["min_potential_total_ml"] = float(user_input["min_potential_total_ml"])
            self._working_options["threshold_mode"] = "fixed_ml"
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="threshold_fixed",
            data_schema=vol.Schema({
                vol.Required(native_option_key("min_potential_total_ml"), default=_bounded(self._working_options.get("min_potential_total_ml"), 500, 50, 5000)): _number(50, 5000, 10, "mL")
            }),
        )

    async def async_step_model(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            submitted = _flatten_sections(user_input)
            candidate = {**self._working_options, **submitted}
            relation_error = option_relationship_error(candidate)
            if relation_error:
                return self.async_show_form(
                    step_id="model",
                    data_schema=_model_schema(candidate),
                    errors={"base": relation_error},
                )
            self._working_options.update(submitted)
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="model", data_schema=_model_schema(self._working_options)
        )

    async def async_step_recommendation_priorities(self, user_input=None):
        """Choose a room and edit its recommendation-goal ranking centrally."""
        self._ensure_working_copy()
        eligible = [r for r in self._rooms() if len(_available_room_goals(r)) > 1]
        if not eligible:
            return await self.async_step_ventilation_settings()
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_ventilation_settings()
            self._selected_room_key = str(user_input["room"])
            return await self.async_step_recommendation_priority_order()
        options = [{"value": r["key"], "label": r.get(CONF_ROOM_NAME, r["key"])} for r in eligible]
        return self.async_show_form(
            step_id="recommendation_priorities",
            data_schema=vol.Schema({
                vol.Optional("wizard_back", default=False): selector.BooleanSelector(),
                vol.Required("room", default=options[0]["value"]): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)),
            }),
        )

    async def async_step_recommendation_priority_order(self, user_input=None):
        room = next((r for r in self._rooms() if r.get("key") == self._selected_room_key), None)
        if room is None:
            return await self.async_step_recommendation_priorities()
        errors = {}
        if user_input is not None:
            if bool(user_input.get("wizard_back")):
                return await self.async_step_recommendation_priorities()
            errors = _goal_priority_errors(user_input, room)
            if not errors:
                room[CONF_ROOM_GOAL_PRIORITIES] = _ranked_goal_priorities(user_input, room)
                # Priority order does not change the room structure. Avoid a
                # config-entry reload while the options dialog is still active.
                self._persist_working_state(reload_entry=False)
                return await self.async_step_recommendation_priorities()
        return self.async_show_form(
            step_id="recommendation_priority_order",
            data_schema=_goal_priority_schema(room, include_back=True),
            errors=errors,
        )

    async def async_step_cross_ventilation(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        room_keys = ", ".join(
            f"{room.get(CONF_ROOM_NAME, room['key'])} = {room['key']}"
            for room in self._rooms()
        ) or _txt(_flow_language(self.hass), "Noch keine Räume eingerichtet", "No rooms set up yet")
        return self.async_show_form(
            step_id="cross_ventilation",
            data_schema=_cross_ventilation_schema(self._working_options),
            description_placeholders={"room_keys": room_keys},
        )

    async def async_step_profile(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["operating_profile"] = user_input[
                "operating_profile"
            ]
            self._persist_working_state()
            if self._working_options["operating_profile"] == PROFILE_SUMMER_COOLING:
                return await self.async_step_profile_details()
            # The efficiency fields for Comfort/Dehumidify already live in the
            # canonical ventilation model. Do not expose duplicate controls.
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="profile", data_schema=_profile_schema(self._working_options)
        )

    async def async_step_profile_details(self, user_input=None):
        if self._working_options.get("operating_profile", PROFILE_COMFORT) != PROFILE_SUMMER_COOLING:
            return await self.async_step_ventilation_settings()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="profile_details",
            data_schema=_profile_details_schema(self._working_options),
            description_placeholders={
                "profile": (
                    _PROFILE_LABELS_DE if _is_de(_flow_language(self.hass)) else _PROFILE_LABELS_EN
                ).get(
                    self._working_options.get("operating_profile", PROFILE_COMFORT),
                    _txt(_flow_language(self.hass), "Komfort", "Comfort"),
                )
            },
        )

    async def async_step_building(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="building", data_schema=_building_schema(self._working_options)
        )

    def _resident_placeholders(self) -> dict[str, str]:
        language = self.hass.config.language if self.hass else "de"
        return {
            "resident_slots": _resident_slot_overview(self._working_options, language),
            **_resident_slot_placeholders(self._working_options, language),
        }

    async def async_step_residents(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            values = _flatten_sections(dict(user_input))
            # Keep the same compact string representation used by the dashboard
            # resident-profile editor so both UIs write exactly one setting.
            # Convert readable per-person controls back to the existing compact profile contract.
            import json
            existing_profiles = _resident_profiles_dict(self._working_options.get("resident_room_profiles"))
            adult_names = _resident_name_list(values.get("adult_resident_names", self._working_options.get("adult_resident_names")))
            child_names = _resident_name_list(values.get("child_resident_names", self._working_options.get("child_resident_names")))
            structured = any(key.startswith(("adult_", "child_")) and key.endswith(("_rooms", "_thermal", "_notifications")) for key in values)
            if structured:
                rebuilt = {}
                for role, names, count in (("adult", adult_names, int(values.get("adult_occupants", self._working_options.get("adult_occupants", 0)) or 0)), ("child", child_names, int(values.get("child_occupants", self._working_options.get("child_occupants", 0)) or 0))):
                    for idx in range(min(max(count, len(names)), 4)):
                        prefix = f"{role}_{idx + 1}"
                        previous = existing_profiles.get(f"{role}:{idx}", {})
                        notifications = str(values.pop(f"{prefix}_notifications", ", ".join(previous.get("notification_targets") or [])) or "")
                        rebuilt[f"{role}:{idx}"] = {
                            "name": names[idx] if idx < len(names) else "",
                            "room_keys": list(values.pop(f"{prefix}_rooms", previous.get("room_keys") or [])),
                            "thermal_preference": str(values.pop(f"{prefix}_thermal", previous.get("thermal_preference") or "inherit")),
                            "notification_targets": [x.strip() for x in notifications.replace(";", ",").split(",") if x.strip()],
                        }
                values["resident_room_profiles"] = json.dumps(rebuilt, ensure_ascii=False, separators=(",", ":"))
            profiles = values.get("resident_room_profiles")
            if isinstance(profiles, str):
                import json
                try:
                    parsed = json.loads(profiles or "{}")
                    if not isinstance(parsed, dict):
                        raise ValueError
                    values["resident_room_profiles"] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    return self.async_show_form(
                        step_id="residents",
                        data_schema=_residents_schema(self._working_options, self._rooms()),
            description_placeholders=self._resident_placeholders(),
                        errors={"base": "resident_profiles_invalid"},
                    )
            self._working_options.update(values)
            self._persist_working_state()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="residents", data_schema=_residents_schema(self._working_options, self._rooms()),
            description_placeholders=self._resident_placeholders()
        )

    async def async_step_house(self, user_input=None):
        """Compatibility route for flows created before the unified settings UI."""
        self._ensure_working_copy()
        if user_input is not None:
            # Still accept a form that was already open before an update, so no
            # user-entered value is lost during a Home Assistant reload.
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        # Do not render the former combined house/resident form again: its
        # fields now live canonically under Gebäude and Bewohner.
        return await self.async_step_home_setup()

    async def async_step_personalisation(self, user_input=None):
        """Compatibility route for the former duplicate personalisation form."""
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_home_setup()
        # Personalisation is part of the unified Bewohner form now.
        return await self.async_step_residents()

    async def async_step_forecast(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="forecast", data_schema=_forecast_schema(self._working_options)
        )

    async def async_step_air_quality(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        return self.async_show_form(
            step_id="air_quality",
            data_schema=_air_quality_schema(self._working_options),
        )

    async def async_step_energy(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["heating_system"] = user_input["heating_system"]
            self._persist_working_state()
            return await self.async_step_energy_details()
        return self.async_show_form(
            step_id="energy", data_schema=_energy_system_schema(self._working_options)
        )

    async def async_step_energy_details(self, user_input=None):
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_notification_energy_settings()
        return self.async_show_form(
            step_id="energy_details",
            data_schema=_energy_details_schema(self._working_options),
            description_placeholders={
                "heating_system": (
                    _HEATING_LABELS_DE if _is_de(_flow_language(self.hass)) else _HEATING_LABELS_EN
                ).get(
                    self._working_options.get("heating_system", HEATING_HEAT_PUMP),
                    _txt(_flow_language(self.hass), "Wärmepumpe", "Heat pump"),
                )
            },
        )

    async def async_step_notifications(self, user_input=None):
        self._ensure_working_copy()
        errors = {}
        if user_input is not None:
            submitted = dict(user_input)
            test_now = bool(submitted.pop("test_notification_now", False))
            self._working_options.update(submitted)
            self._persist_working_state()
            if test_now:
                targets = _all_notification_targets({**DEFAULT_OPTIONS, **self._working_options})
                if not targets:
                    errors["test_notification_now"] = "notification_test_no_target"
                else:
                    sent = await _send_targets(
                        self.hass, targets, "FreshAirIQ · Test",
                        "Test erfolgreich: FreshAirIQ kann dieses Benachrichtigungsziel erreichen.",
                    )
                    if not sent:
                        errors["test_notification_now"] = "notification_test_failed"
                return self.async_show_form(
                    step_id="notifications",
                    data_schema=_notification_schema(self.hass, self._working_options, self._rooms()),
                    errors=errors,
                )
            return await self.async_step_notification_energy_settings()
        return self.async_show_form(
            step_id="notifications",
            data_schema=_notification_schema(self.hass, self._working_options, self._rooms()),
        )

    async def async_step_statistics(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options["statistics_days"] = int(
                user_input["statistics_days"]
            )
            self._persist_working_state()
            return await self.async_step_data_learning_settings()
        return self.async_show_form(
            step_id="statistics",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        native_option_key("statistics_days"),
                        default=_safe_int(self._working_options.get("statistics_days"), 14, minimum=1, maximum=365),
                    ): _number(1, 365, 1, "Tage")
                }
            ),
        )

    async def async_step_diagnostics_sharing(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_data_learning_settings()
        return self.async_show_form(
            step_id="diagnostics_sharing",
            data_schema=_diagnostics_sharing_schema(self._working_options),
        )

    async def async_step_reset_defaults(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            if user_input.get("confirm"):
                self._working_options = dict(DEFAULT_OPTIONS)
                self._persist_working_state()
            return await self.async_step_maintenance()
        return self.async_show_form(
            step_id="reset_defaults",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_reset_learning(self, user_input=None):
        if user_input is not None:
            if user_input.get("confirm"):
                coordinator = getattr(self.config_entry, "runtime_data", None)
                if coordinator:
                    await coordinator.store.async_reset_learning()
                    await coordinator.async_request_refresh()
            return await self.async_step_maintenance()
        return self.async_show_form(
            step_id="reset_learning",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_back_to_main(self, user_input=None):
        return await self.async_step_init()

    async def async_step_back_to_home_setup(self, user_input=None):
        return await self.async_step_home_setup()

    # Legacy generic back target.
    async def async_step_back(self, user_input=None):
        return await self.async_step_init()

    async def async_step_finish(self, user_input=None):
        return self._commit_and_close()


# 0.26.4.3: unexpected step exceptions are recorded (and, with consent, reported)
# instead of disappearing behind Home Assistant's "Unknown error occurred".
from .flow_errors import guard_flow_steps  # noqa: E402

guard_flow_steps(FreshAirIQConfigFlow, "config_flow")
guard_flow_steps(FreshAirIQRoomSubentryFlow, "room_flow")
guard_flow_steps(FreshAirIQOptionsFlow, "options_flow")

