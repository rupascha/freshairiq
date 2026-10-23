"""Room forms of the config flows: room schemas, per-opening references and normalisation of submitted room data."""
from __future__ import annotations

import re
import voluptuous as vol
from copy import deepcopy
from typing import Any

from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_CONTACT_COVERS,
    CONF_CONTACT_COVER_FOLLOW,
    CONF_CONTACT_DELAY,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_PASSAGE_DOORS,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_ROOMS,
    CONF_ROOM_AIR_PURIFIER,
    CONF_ROOM_AUTO_SUN_PROTECTION,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_CONTACT,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_COVERS,
    CONF_ROOM_DEHUMIDIFIER,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY,
    CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE,
    CONF_ROOM_EXHAUST_FAN_CONTROL,
    CONF_ROOM_EXHAUST_FAN_FOLLOW_UP,
    CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME,
    CONF_ROOM_FLOOR,
    CONF_ROOM_DISABLED_GOALS,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HEIGHT,
    CONF_ROOM_HUMIDIFIER,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_HUMIDITY_AGGREGATION,
    CONF_ROOM_ICON,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_LENGTH,
    CONF_ROOM_MOISTURE_SOURCES,
    CONF_ROOM_NAME,
    CONF_ROOM_PM25,
    CONF_ROOM_REFERENCE_HUMIDITY,
    CONF_ROOM_REFERENCE_TEMPERATURE,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_SUPPLY_FAN,
    CONF_ROOM_TARGET_TEMPERATURE,
    CONF_ROOM_TARGET_TEMPERATURE_FALLBACK,
    CONF_ROOM_TARGET_TEMPERATURE_MODE,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_TEMPERATURE_AGGREGATION,
    CONF_ROOM_THRESHOLD_ML,
    CONF_ROOM_THRESHOLD_MODE,
    CONF_ROOM_THRESHOLD_PERCENT,
    CONF_ROOM_VENTILATION_DEVICE,
    CONF_ROOM_VOC,
    CONF_ROOM_VOLUME,
    CONF_ROOM_WIDTH,
    CONF_ROOM_WINDOW_ORIENTATION,
    CONTACT_MODE_ALL,
    CONTACT_MODE_ANY,
    FLOOR_GROUND,
    MOISTURE_SOURCES,
    ORIENTATIONS,
    ORIENTATION_UNKNOWN,
    ROOM_THRESHOLD_AUTOMATIC,
    ROOM_THRESHOLD_FIXED,
    ROOM_THRESHOLD_PERCENT,
)
from .actuator_control import (
    DEFAULT_FAN_FOLLOW_UP_MIN,
    DEFAULT_FAN_MAX_RUNTIME_MIN,
    FAN_CONTROL_MODES,
    FAN_CONTROL_OFF,
)
from .config_flow_fields import (
    _bounded,
    _choice,
    _climate_sensor_selector,
    _entity_list,
    _number,
    _number_or_none,
    _optional,
    _required,
    _safe_int,
    _slug,
)
from .goals import normalise_disabled_goals
from .config_flow_goals import _filter_room_priorities


# Legacy room-level reference keys remain readable for migration only: CONF_ROOM_REFERENCE_TEMPERATURE, CONF_ROOM_REFERENCE_HUMIDITY
def _room_schema(room: dict[str, Any] | None = None, levels: list[str] | None = None) -> vol.Schema:
    room = room or {}
    levels = list(dict.fromkeys(levels or []))
    return vol.Schema({
        _required(CONF_ROOM_NAME, room.get(CONF_ROOM_NAME)): selector.TextSelector(),
        _optional(CONF_ROOM_ICON, room.get(CONF_ROOM_ICON)): selector.IconSelector(),
        _optional(CONF_ROOM_TEMPERATURE, _entity_list(room.get(CONF_ROOM_TEMPERATURE))): _climate_sensor_selector(device_class="temperature", multiple=True),
        _optional(CONF_ROOM_HUMIDITY, _entity_list(room.get(CONF_ROOM_HUMIDITY))): _climate_sensor_selector(device_class="humidity", multiple=True),
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
            selector.EntitySelectorConfig(domain="sensor")
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
        _optional(CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE, room.get(CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE)): _climate_sensor_selector(device_class="temperature"),
        _optional(CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY, room.get(CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY)): _climate_sensor_selector(device_class="humidity"),
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
            _optional(CONF_ROOM_TEMPERATURE, _entity_list(room.get(CONF_ROOM_TEMPERATURE))): _climate_sensor_selector(device_class="temperature", multiple=True),
            _optional(CONF_ROOM_HUMIDITY, _entity_list(room.get(CONF_ROOM_HUMIDITY))): _climate_sensor_selector(device_class="humidity", multiple=True),
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
            _optional(CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE, room.get(CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE)): _climate_sensor_selector(device_class="temperature"),
            _optional(CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY, room.get(CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY)): _climate_sensor_selector(device_class="humidity"),
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
                selector.EntitySelectorConfig(domain="sensor")
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
        # 0.26.5.1: FreshAirIQ only switches devices when enabled here
        vol.Optional("automation"): section(vol.Schema({
            vol.Required(CONF_ROOM_AUTO_SUN_PROTECTION, default=bool(room.get(CONF_ROOM_AUTO_SUN_PROTECTION, False))): selector.BooleanSelector(),
            vol.Required(CONF_ROOM_EXHAUST_FAN_CONTROL, default=_choice(room.get(CONF_ROOM_EXHAUST_FAN_CONTROL), FAN_CONTROL_OFF, FAN_CONTROL_MODES)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=FAN_CONTROL_MODES, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="exhaust_fan_control")
            ),
            vol.Required(CONF_ROOM_EXHAUST_FAN_FOLLOW_UP, default=_bounded(room.get(CONF_ROOM_EXHAUST_FAN_FOLLOW_UP), DEFAULT_FAN_FOLLOW_UP_MIN, 0, 60)): _number(0, 60, 1, "min"),
            vol.Required(CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME, default=_bounded(room.get(CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME), DEFAULT_FAN_MAX_RUNTIME_MIN, 5, 240)): _number(5, 240, 5, "min"),
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
            _climate_sensor_selector(device_class="temperature"),
        (vol.Optional("reference_humidity", default=humidity) if humidity else vol.Optional("reference_humidity")):
            _climate_sensor_selector(device_class="humidity"),
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
        vol.Optional("cover_follow", default=bool((room.get(CONF_CONTACT_COVER_FOLLOW) or {}).get(contact, False))):
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
    follow = dict(room.get(CONF_CONTACT_COVER_FOLLOW) or {})
    follow[contact] = bool(user_input.get("cover_follow", False) and selected_covers)
    room[CONF_CONTACT_COVER_FOLLOW] = follow
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

    # 0.26.5.3: the neighbouring-room air of an exhaust fan is an atomic pair
    if bool(user_input.get(CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE)) != bool(user_input.get(CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY)):
        errors["base"] = "exhaust_reference_pair_required"
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
        CONF_ROOM_WINDOW_ORIENTATION: room.get(CONF_ROOM_WINDOW_ORIENTATION, previous.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)),
        CONF_ROOM_INCLUDE_CALCULATIONS: include,
        CONF_ROOM_MOISTURE_SOURCES: list(moisture_sources),
        CONF_ROOM_GOAL_PRIORITIES: priorities,
        # 0.26.5.3: goals switched "off" survive an edit of the room's other pages
        CONF_ROOM_DISABLED_GOALS: normalise_disabled_goals(room.get(CONF_ROOM_DISABLED_GOALS, previous.get(CONF_ROOM_DISABLED_GOALS))),
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
        CONF_CONTACT_COVER_FOLLOW: deepcopy(previous.get(CONF_CONTACT_COVER_FOLLOW, {})),
    })
    _normalise_room_control(room, previous)
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
    room[CONF_CONTACT_COVER_FOLLOW] = {
        c: True for c in contacts if room[CONF_CONTACT_COVER_FOLLOW].get(c) and room[CONF_CONTACT_COVERS].get(c)
    }
    return room, {}


def _normalise_room_control(room: dict[str, Any], previous: dict[str, Any]) -> None:
    """0.26.5.1: automatic cover/fan control; values missing from a form keep the stored ones."""
    room[CONF_ROOM_AUTO_SUN_PROTECTION] = bool(room.get(CONF_ROOM_AUTO_SUN_PROTECTION, previous.get(CONF_ROOM_AUTO_SUN_PROTECTION, False)))
    room[CONF_ROOM_EXHAUST_FAN_CONTROL] = _choice(
        room.get(CONF_ROOM_EXHAUST_FAN_CONTROL, previous.get(CONF_ROOM_EXHAUST_FAN_CONTROL)), FAN_CONTROL_OFF, FAN_CONTROL_MODES,
    )
    room[CONF_ROOM_EXHAUST_FAN_FOLLOW_UP] = _bounded(
        room.get(CONF_ROOM_EXHAUST_FAN_FOLLOW_UP, previous.get(CONF_ROOM_EXHAUST_FAN_FOLLOW_UP)), DEFAULT_FAN_FOLLOW_UP_MIN, 0, 60,
    )
    room[CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME] = _bounded(
        room.get(CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME, previous.get(CONF_ROOM_EXHAUST_FAN_MAX_RUNTIME)), DEFAULT_FAN_MAX_RUNTIME_MIN, 5, 240,
    )


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
