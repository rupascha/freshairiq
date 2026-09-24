"""Config and options flows for FreshAirIQ."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector

from .const import *
from .settings_contract import native_option_key
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


def _slug(name: str) -> str:
    value = name.lower().strip().translate(str.maketrans("äöüß", "aous"))
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "room"


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
    return vol.Optional(key, default=value) if value not in (None, "") else vol.Optional(key)



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


def _room_schema(room: dict[str, Any] | None = None, levels: list[str] | None = None) -> vol.Schema:
    room = room or {}
    levels = list(dict.fromkeys(levels or []))
    return vol.Schema({
        _required(CONF_ROOM_NAME, room.get(CONF_ROOM_NAME)): selector.TextSelector(),
        _optional(CONF_ROOM_TEMPERATURE, room.get(CONF_ROOM_TEMPERATURE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        _optional(CONF_ROOM_HUMIDITY, room.get(CONF_ROOM_HUMIDITY)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
        ),
        vol.Optional(CONF_ROOM_CONTACTS, default=room.get(CONF_ROOM_CONTACTS, [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
        ),
        vol.Required(CONF_CONTACT_MODE, default=room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[CONTACT_MODE_ANY, CONTACT_MODE_ALL], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="contact_mode")
        ),
        # No volume-mode selector: users may provide a direct m³ value OR dimensions.
        _optional(CONF_ROOM_VOLUME, room.get(CONF_ROOM_VOLUME)): _number(2, 1000, 0.1, "m³"),
        _optional(CONF_ROOM_LENGTH, room.get(CONF_ROOM_LENGTH)): _number(0.5, 100, 0.01, "m"),
        _optional(CONF_ROOM_WIDTH, room.get(CONF_ROOM_WIDTH)): _number(0.5, 100, 0.01, "m"),
        _optional(CONF_ROOM_HEIGHT, room.get(CONF_ROOM_HEIGHT)): _number(1, 20, 0.01, "m"),
        _optional(CONF_ROOM_REFERENCE_TEMPERATURE, room.get(CONF_ROOM_REFERENCE_TEMPERATURE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        _optional(CONF_ROOM_REFERENCE_HUMIDITY, room.get(CONF_ROOM_REFERENCE_HUMIDITY)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        _optional(CONF_ROOM_CO2, room.get(CONF_ROOM_CO2)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide")
        ),
        _optional(CONF_ROOM_VOC, room.get(CONF_ROOM_VOC)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        _optional(CONF_ROOM_PM25, room.get(CONF_ROOM_PM25)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        _optional(CONF_ROOM_ILLUMINANCE, room.get(CONF_ROOM_ILLUMINANCE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        _optional(CONF_ROOM_CLIMATE, room.get(CONF_ROOM_CLIMATE)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        _optional(CONF_ROOM_EXHAUST_FAN, room.get(CONF_ROOM_EXHAUST_FAN)): selector.EntitySelector(),
        _optional(CONF_ROOM_SUPPLY_FAN, room.get(CONF_ROOM_SUPPLY_FAN)): selector.EntitySelector(),
        _optional(CONF_ROOM_VENTILATION_DEVICE, room.get(CONF_ROOM_VENTILATION_DEVICE)): selector.EntitySelector(),
        _optional(CONF_ROOM_DEHUMIDIFIER, room.get(CONF_ROOM_DEHUMIDIFIER)): selector.EntitySelector(),
        _optional(CONF_ROOM_HUMIDIFIER, room.get(CONF_ROOM_HUMIDIFIER)): selector.EntitySelector(),
        _optional(CONF_ROOM_AIR_PURIFIER, room.get(CONF_ROOM_AIR_PURIFIER)): selector.EntitySelector(),
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
            _optional(CONF_ROOM_TEMPERATURE, room.get(CONF_ROOM_TEMPERATURE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            _optional(CONF_ROOM_HUMIDITY, room.get(CONF_ROOM_HUMIDITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
            ),
            vol.Optional(CONF_ROOM_CONTACTS, default=room.get(CONF_ROOM_CONTACTS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Required(CONF_CONTACT_MODE, default=room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[CONTACT_MODE_ANY, CONTACT_MODE_ALL], mode=selector.SelectSelectorMode.DROPDOWN, translation_key="contact_mode")
            ),
        }), {"collapsed": False}),
        vol.Required("geometry"): section(vol.Schema({
            _optional(CONF_ROOM_VOLUME, room.get(CONF_ROOM_VOLUME)): _number(2, 1000, 0.1, "m³"),
            _optional(CONF_ROOM_LENGTH, room.get(CONF_ROOM_LENGTH)): _number(0.5, 100, 0.01, "m"),
            _optional(CONF_ROOM_WIDTH, room.get(CONF_ROOM_WIDTH)): _number(0.5, 100, 0.01, "m"),
            _optional(CONF_ROOM_HEIGHT, room.get(CONF_ROOM_HEIGHT)): _number(1, 20, 0.01, "m"),
        }), {"collapsed": True}),
        vol.Optional("optional_sensors"): section(vol.Schema({
            _optional(CONF_ROOM_REFERENCE_TEMPERATURE, room.get(CONF_ROOM_REFERENCE_TEMPERATURE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            _optional(CONF_ROOM_REFERENCE_HUMIDITY, room.get(CONF_ROOM_REFERENCE_HUMIDITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            _optional(CONF_ROOM_CO2, room.get(CONF_ROOM_CO2)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="carbon_dioxide")
            ),
            _optional(CONF_ROOM_VOC, room.get(CONF_ROOM_VOC)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            _optional(CONF_ROOM_PM25, room.get(CONF_ROOM_PM25)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            _optional(CONF_ROOM_ILLUMINANCE, room.get(CONF_ROOM_ILLUMINANCE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }), {"collapsed": True}),
        vol.Optional("optional_actuators"): section(vol.Schema({
            _optional(CONF_ROOM_CLIMATE, room.get(CONF_ROOM_CLIMATE)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),
            _optional(CONF_ROOM_EXHAUST_FAN, room.get(CONF_ROOM_EXHAUST_FAN)): selector.EntitySelector(),
            _optional(CONF_ROOM_SUPPLY_FAN, room.get(CONF_ROOM_SUPPLY_FAN)): selector.EntitySelector(),
            _optional(CONF_ROOM_VENTILATION_DEVICE, room.get(CONF_ROOM_VENTILATION_DEVICE)): selector.EntitySelector(),
            _optional(CONF_ROOM_DEHUMIDIFIER, room.get(CONF_ROOM_DEHUMIDIFIER)): selector.EntitySelector(),
            _optional(CONF_ROOM_HUMIDIFIER, room.get(CONF_ROOM_HUMIDIFIER)): selector.EntitySelector(),
            _optional(CONF_ROOM_AIR_PURIFIER, room.get(CONF_ROOM_AIR_PURIFIER)): selector.EntitySelector(),
        }), {"collapsed": True}),
    })


def _contact_reference_field(contact: str, kind: str) -> str:
    return f"{contact}__freshairiq_reference_{kind}"


def _contact_reference_schema(room: dict[str, Any], hass=None) -> vol.Schema:
    """Build one temperature/humidity reference pair per configured opening.

    Reference-air selectors intentionally accept every sensor entity. A number
    of perfectly valid Home Assistant sensors expose °C/% but no device_class;
    filtering those out made local zones such as conservatories impossible to
    select. Runtime plausibility checks still reject unusable numeric states.
    """
    fields: dict[Any, Any] = {}
    temperatures = room.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    humidities = room.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    covers = room.get(CONF_CONTACT_COVERS) or {}
    for contact in room.get(CONF_ROOM_CONTACTS, []) or []:
        state = hass.states.get(contact) if hass is not None else None
        label = str((state.attributes or {}).get("friendly_name") or contact) if state else str(contact)
        temp_key = _contact_reference_field(str(contact), "temperature")
        humidity_key = _contact_reference_field(str(contact), "humidity")
        temp = str(temperatures.get(contact) or "").strip()
        humidity = str(humidities.get(contact) or "").strip()
        temp_marker = vol.Optional(temp_key, default=temp, description=f"{label} · Referenztemperatur") if temp else vol.Optional(temp_key, description=f"{label} · Referenztemperatur")
        humidity_marker = vol.Optional(humidity_key, default=humidity, description=f"{label} · Referenzfeuchte") if humidity else vol.Optional(humidity_key, description=f"{label} · Referenzfeuchte")
        cover_key = _contact_reference_field(str(contact), "covers")
        contact_covers = list(covers.get(contact) or [])
        cover_marker = vol.Optional(cover_key, default=contact_covers, description=f"{label} · Rollo/Jalousie")
        fields[temp_marker] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        fields[humidity_marker] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        fields[cover_marker] = selector.EntitySelector(selector.EntitySelectorConfig(domain="cover", multiple=True))
    return vol.Schema(fields)


def _apply_contact_references(room: dict[str, Any], user_input: dict[str, Any]) -> bool:
    """Apply atomic per-opening reference pairs; return False for partial pairs."""
    temperatures: dict[str, str] = {}
    humidities: dict[str, str] = {}
    contact_covers: dict[str, list[str]] = {}
    for contact in room.get(CONF_ROOM_CONTACTS, []) or []:
        contact = str(contact)
        temp = str(user_input.get(_contact_reference_field(contact, "temperature")) or "").strip()
        humidity = str(user_input.get(_contact_reference_field(contact, "humidity")) or "").strip()
        if bool(temp) != bool(humidity):
            return False
        if temp and humidity:
            temperatures[contact] = temp
            humidities[contact] = humidity
        raw_covers = user_input.get(_contact_reference_field(contact, "covers")) or []
        if isinstance(raw_covers, str):
            raw_covers = [raw_covers]
        selected_covers = [str(entity_id) for entity_id in raw_covers if str(entity_id).startswith("cover.")]
        if selected_covers:
            contact_covers[contact] = list(dict.fromkeys(selected_covers))
    room[CONF_CONTACT_REFERENCE_TEMPERATURES] = temperatures
    room[CONF_CONTACT_REFERENCE_HUMIDITIES] = humidities
    room[CONF_CONTACT_COVERS] = contact_covers
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
    if include and not contacts:
        errors[CONF_ROOM_CONTACTS] = "ventilation_contact_required"

    volume = _number_or_none(user_input.get(CONF_ROOM_VOLUME))
    length = _number_or_none(user_input.get(CONF_ROOM_LENGTH))
    width = _number_or_none(user_input.get(CONF_ROOM_WIDTH))
    height = _number_or_none(user_input.get(CONF_ROOM_HEIGHT))
    dimensions_complete = all(v is not None and v > 0 for v in (length, width, height))
    if volume is None and not dimensions_complete:
        errors["base"] = "room_volume_required"
    elif volume is not None and volume < 2:
        errors[CONF_ROOM_VOLUME] = "room_volume_too_small"
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
    room.update({
        "key": key,
        CONF_ROOM_NAME: name,
        CONF_ROOM_CONTACTS: list(contacts),
        CONF_CONTACT_MODE: room.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY),
        CONF_ROOM_FLOOR: str(room.get(CONF_ROOM_FLOOR, "")).strip() or "Unzugeordnet",
        CONF_ROOM_WINDOW_ORIENTATION: room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN),
        CONF_ROOM_INCLUDE_CALCULATIONS: include,
        CONF_ROOM_MOISTURE_SOURCES: list(moisture_sources),
        CONF_ROOM_THRESHOLD_MODE: _choice(room.get(CONF_ROOM_THRESHOLD_MODE), ROOM_THRESHOLD_AUTOMATIC, [ROOM_THRESHOLD_AUTOMATIC, ROOM_THRESHOLD_PERCENT, ROOM_THRESHOLD_FIXED]),
        CONF_ROOM_THRESHOLD_PERCENT: _bounded(room.get(CONF_ROOM_THRESHOLD_PERCENT), 5, 1, 30),
        CONF_ROOM_THRESHOLD_ML: _bounded(room.get(CONF_ROOM_THRESHOLD_ML), 100, 10, 1000),
        CONF_ROOM_SORT_ORDER: _safe_int(previous.get(CONF_ROOM_SORT_ORDER), len(existing_rooms), minimum=0),
        CONF_CONTACT_DELAYS: dict(previous.get(CONF_CONTACT_DELAYS, {})),
        CONF_CONTACT_ORIENTATIONS: dict(previous.get(CONF_CONTACT_ORIENTATIONS, {})),
        CONF_CONTACT_REFERENCE_TEMPERATURES: dict(previous.get(CONF_CONTACT_REFERENCE_TEMPERATURES, {})),
        CONF_CONTACT_REFERENCE_HUMIDITIES: dict(previous.get(CONF_CONTACT_REFERENCE_HUMIDITIES, {})),
        CONF_CONTACT_COVERS: deepcopy(previous.get(CONF_CONTACT_COVERS, {})),
    })
    # If all dimensions are present they are the source of truth; otherwise use
    # the direct m³ value. This keeps dimension-based rooms editable without a
    # separate and confusing "volume mode" selector.
    if dimensions_complete:
        room[CONF_ROOM_LENGTH] = length; room[CONF_ROOM_WIDTH] = width; room[CONF_ROOM_HEIGHT] = height
        room[CONF_ROOM_VOLUME] = round(length * width * height, 3)
    else:
        room[CONF_ROOM_VOLUME] = round(volume, 3)
        room.pop(CONF_ROOM_LENGTH, None); room.pop(CONF_ROOM_WIDTH, None); room.pop(CONF_ROOM_HEIGHT, None)
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

def _level_label(value: Any) -> str:
    """Human-readable label for legacy and user-defined levels/zones."""
    raw = str(value or "").strip()
    return _LEGACY_LEVEL_LABELS.get(raw, raw or "Nicht zugeordnet")

def _level_options(levels: list[str]) -> list[dict[str, str]]:
    return [{"value": x, "label": _level_label(x)} for x in levels]


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


def _residents_schema(current: dict[str, Any]) -> vol.Schema:
    """Unified resident/presence/personalisation form used by native HA UI."""
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
        vol.Optional("resident_profiles"): section(vol.Schema({
            vol.Optional(native_option_key("resident_room_profiles"), default=str(current.get("resident_room_profiles", "{}"))): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        }), {"collapsed": True}),
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
    })



def _diagnostics_sharing_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(
            native_option_key("diagnostics_reporting_mode"),
            default=str(current.get("diagnostics_reporting_mode", "daily")),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "off", "label": "Aus"},
                    {"value": "errors", "label": "Nur bei erkannten Problemen"},
                    {"value": "daily", "label": "Täglich nachts"},
                    {"value": "weekly", "label": "Wöchentlich"},
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
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
    services = sorted((hass.services.async_services().get("notify") or {}).keys())
    targets = [{"value": s, "label": f"notify.{s}"} for s in services]
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
        if room is None or not room.get(CONF_ROOM_CONTACTS):
            return await self.async_step_more_rooms()
        errors = {}
        if user_input is not None:
            if _apply_contact_references(room, user_input):
                return await self.async_step_more_rooms()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="room_references",
            data_schema=_contact_reference_schema(room, self.hass),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, room.get("key", "Raum"))},
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

    Rooms are deliberately modelled as config subentries. This keeps global
    FreshAirIQ settings on the parent entry while room-specific settings can be
    opened and edited directly from the room entry in Home Assistant.
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
        """Add a room from the integration's native subentry UI."""
        rooms = self._entry_rooms()
        levels = self._levels()
        errors = {}
        if user_input is not None:
            room, errors = _normalise_room(user_input, rooms)
            if room and not errors:
                self._working_room = room
                self._room_key = room["key"]
                return await self.async_step_add_orientations()
        return self.async_show_form(step_id="user", data_schema=_room_section_schema(levels=levels), errors=errors)

    async def async_step_add_orientations(self, user_input=None):
        room = self._working_room or {}
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self.async_step_add_delays(user_input={})
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {
                contact: str(user_input.get(contact, ORIENTATION_UNKNOWN)) for contact in contacts
            }
            return await self.async_step_add_delays()
        current = room.get(CONF_CONTACT_ORIENTATIONS, {})
        return self.async_show_form(
            step_id="add_orientations",
            data_schema=vol.Schema({
                vol.Required(contact, default=str(current.get(contact, ORIENTATION_UNKNOWN))): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ORIENTATIONS, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="window_orientation")
                ) for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )

    async def async_step_add_delays(self, user_input=None):
        room = self._working_room or {}
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if user_input is not None:
            room[CONF_CONTACT_DELAYS] = {contact: _safe_int(user_input.get(contact, 0), 0, minimum=0, maximum=600) for contact in contacts}
            return await self.async_step_add_references()
        current = room.get(CONF_CONTACT_DELAYS, {})
        return self.async_show_form(
            step_id="add_delays",
            data_schema=vol.Schema({
                vol.Optional(contact, default=_safe_int(current.get(contact, 0), 0, minimum=0, maximum=600)): _number(0, 600, 1, "s")
                for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )

    async def async_step_add_references(self, user_input=None):
        room = self._working_room or {}
        if not room.get(CONF_ROOM_CONTACTS) and user_input is None:
            user_input = {}
        errors = {}
        if user_input is not None:
            if not _apply_contact_references(room, user_input):
                errors["base"] = "contact_reference_pair_required"
            else:
                entry = self._get_entry()
                rooms = self._entry_rooms()
                rooms.append(room)
                data = dict(entry.data)
                data[CONF_ROOMS] = rooms
                levels = list(data.get(CONF_LEVELS, []))
                if room.get(CONF_ROOM_FLOOR) and room[CONF_ROOM_FLOOR] not in levels:
                    levels.append(room[CONF_ROOM_FLOOR])
                data[CONF_LEVELS] = levels
                self.hass.config_entries.async_update_entry(entry, data=data)
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(
                    title=room.get(CONF_ROOM_NAME, room["key"]),
                    data=room,
                    unique_id=f"room:{room['key']}",
                )
        return self.async_show_form(
            step_id="add_references",
            data_schema=_contact_reference_schema(room, self.hass),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )


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
            title=room.get(CONF_ROOM_NAME, self._room_key or "Raum"),
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)

    async def async_step_reconfigure(self, user_input=None):
        """Open a clear room-local settings menu."""
        self._current_room()
        room = self._current_room()
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["room_basics", "room_orientations", "room_delays", "room_references", "save_room"],
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
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
                return await self.async_step_reconfigure()
        return self.async_show_form(
            step_id="room_basics",
            data_schema=_room_section_schema(room, self._levels()),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )

    async def async_step_room_orientations(self, user_input=None):
        room = self._current_room()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self.async_step_reconfigure()
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {
                contact: str(user_input.get(contact, ORIENTATION_UNKNOWN)) for contact in contacts
            }
            self._persist_room_update()
            return await self.async_step_reconfigure()
        current = room.get(CONF_CONTACT_ORIENTATIONS, {})
        fallback = room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)
        return self.async_show_form(
            step_id="room_orientations",
            data_schema=vol.Schema({
                vol.Required(contact, default=str(current.get(contact, fallback))): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ORIENTATIONS, mode=selector.SelectSelectorMode.DROPDOWN, translation_key="window_orientation")
                ) for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )

    async def async_step_room_delays(self, user_input=None):
        room = self._current_room()
        contacts = room.get(CONF_ROOM_CONTACTS, [])
        if not contacts:
            return await self.async_step_reconfigure()
        if user_input is not None:
            room[CONF_CONTACT_DELAYS] = {contact: _safe_int(user_input.get(contact, 0), 0, minimum=0, maximum=600) for contact in contacts}
            self._persist_room_update()
            return await self.async_step_reconfigure()
        current = room.get(CONF_CONTACT_DELAYS, {})
        return self.async_show_form(
            step_id="room_delays",
            data_schema=vol.Schema({
                vol.Optional(contact, default=_safe_int(current.get(contact, room.get(CONF_CONTACT_DELAY, 0)), 0, minimum=0, maximum=600)): _number(0, 600, 1, "s")
                for contact in contacts
            }),
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
        )

    async def async_step_room_references(self, user_input=None):
        room = self._current_room()
        if not room.get(CONF_ROOM_CONTACTS):
            return await self.async_step_reconfigure()
        errors = {}
        if user_input is not None:
            if _apply_contact_references(room, user_input):
                self._persist_room_update()
                return await self.async_step_reconfigure()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="room_references",
            data_schema=_contact_reference_schema(room, self.hass),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, self._room_key or "Raum")},
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
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        # Native subentry helper keeps Home Assistant's subentry state in sync.
        return self.async_update_and_abort(
            entry,
            subentry,
            data=dict(room),
            title=room.get(CONF_ROOM_NAME, self._room_key or "Raum"),
        )


class FreshAirIQOptionsFlow(config_entries.OptionsFlowWithReload):
    def __init__(self) -> None:
        self._working_data = None; self._working_options = None; self._selected_room_key = None

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
            structural_change = CONF_ROOMS in changed_data_keys
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
                        if "diagnostics_reporting_mode" in changed_option_keys:
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
        # Global room administration only. Per-room sensors, directions and
        # contact delays also remain available on each native room subentry.
        menu = ["add_room"]
        if self._rooms():
            menu.extend(["edit_room_select", "sort_rooms", "remove_room"])
        menu.append("back_to_home_setup")
        return self.async_show_menu(step_id="rooms", menu_options=menu)

    async def async_step_add_room(self, user_input=None):
        errors = {}
        if user_input is not None:
            room, errors = _normalise_room(user_input, self._rooms())
            if room and not errors:
                self._rooms().append(room)
                self._selected_room_key = room["key"]
                # Save the valid base room immediately. Direction/delay forms
                # enrich the same room on the next screens.
                self._persist_working_state()
                return await self.async_step_contact_orientations()
        return self.async_show_form(
            step_id="add_room",
            data_schema=_room_section_schema(
                levels=list(self._working_data.get(CONF_LEVELS, []))
            ),
            errors=errors,
        )

    async def async_step_edit_room_select(self, user_input=None):
        if user_input is not None:
            self._selected_room_key = user_input["room"]
            return await self.async_step_edit_room()
        return self.async_show_form(
            step_id="edit_room_select",
            data_schema=vol.Schema({vol.Required("room"): self._room_selector()}),
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
                self._persist_working_state()
                return await self.async_step_contact_orientations()
        return self.async_show_form(
            step_id="edit_room",
            data_schema=_room_section_schema(
                room, list(self._working_data.get(CONF_LEVELS, []))
            ),
            errors=errors,
            description_placeholders={"room_name": room.get("name", room["key"])},
        )

    async def async_step_sort_rooms(self, user_input=None):
        rooms = self._rooms()
        if user_input is not None:
            indexed = {r["key"]: i for i, r in enumerate(rooms)}
            ordered_rooms = sorted(
                rooms,
                key=lambda r: (
                    int(user_input.get(r["key"], indexed[r["key"]] + 1)),
                    indexed[r["key"]],
                ),
            )
            for i, room in enumerate(ordered_rooms):
                room[CONF_ROOM_SORT_ORDER] = i
            self._working_data[CONF_ROOMS] = ordered_rooms
            self._persist_working_state()
            return await self.async_step_rooms()
        fields = {}
        for idx, room in enumerate(rooms, start=1):
            label = (
                f"{_level_label(room.get(CONF_ROOM_FLOOR))} · "
                f"{room.get(CONF_ROOM_NAME, room['key'])}"
            )
            fields[
                vol.Required(room["key"], default=idx, description=label)
            ] = _number(1, max(len(rooms), 1), 1)
        return self.async_show_form(
            step_id="sort_rooms", data_schema=vol.Schema(fields)
        )

    async def async_step_contact_orientations_room(self, user_input=None):
        if user_input is not None:
            self._selected_room_key = user_input["room"]
            return await self.async_step_contact_orientations()
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
            return await self.async_step_rooms()
        if user_input is not None:
            room[CONF_CONTACT_ORIENTATIONS] = {
                c: str(user_input.get(c, ORIENTATION_UNKNOWN)) for c in contacts
            }
            self._persist_working_state()
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
            self._persist_working_state()
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
        if room is None:
            return await self.async_step_rooms()
        if not room.get(CONF_ROOM_CONTACTS):
            return await self.async_step_rooms()
        errors = {}
        if user_input is not None:
            if _apply_contact_references(room, user_input):
                self._persist_working_state()
                return await self.async_step_rooms()
            errors["base"] = "contact_reference_pair_required"
        return self.async_show_form(
            step_id="contact_references",
            data_schema=_contact_reference_schema(room, self.hass),
            errors=errors,
            description_placeholders={"room_name": room.get(CONF_ROOM_NAME, room.get("key", "Raum"))},
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
                            options=[
                                {"value": "add", "label": "Bereich hinzufügen"},
                                {"value": "reorder", "label": "Bereiche sortieren"},
                                {"value": "remove", "label": "Bereich entfernen"},
                                {"value": "back", "label": "← Zurück zu Zuhause & Räume"},
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={
                "levels": ", ".join(_level_label(x) for x in levels)
                if levels
                else "Noch keine Bereiche"
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
                    int(user_input.get(_level_label(level), indexed[level] + 1)),
                    indexed[level],
                ),
            )
            self._working_data[CONF_LEVELS] = ordered
            self._persist_working_state()
            return await self.async_step_levels()
        fields = {
            vol.Required(_level_label(level), default=idx): _number(
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
        opts = [{"value": x, "label": _level_label(x)} for x in removable]
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

    async def async_step_cross_ventilation(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_ventilation_settings()
        room_keys = ", ".join(
            f"{room.get(CONF_ROOM_NAME, room['key'])} = {room['key']}"
            for room in self._rooms()
        ) or "Noch keine Räume eingerichtet"
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
                "profile": _PROFILE_LABELS_DE.get(
                    self._working_options.get("operating_profile", PROFILE_COMFORT),
                    "Komfort",
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

    async def async_step_residents(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            values = _flatten_sections(dict(user_input))
            # Keep the same compact string representation used by the dashboard
            # resident-profile editor so both UIs write exactly one setting.
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
                        data_schema=_residents_schema(self._working_options),
                        errors={"base": "resident_profiles_invalid"},
                    )
            self._working_options.update(values)
            self._persist_working_state()
            return await self.async_step_home_setup()
        return self.async_show_form(
            step_id="residents", data_schema=_residents_schema(self._working_options)
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
                "heating_system": _HEATING_LABELS_DE.get(
                    self._working_options.get("heating_system", HEATING_HEAT_PUMP),
                    "Wärmepumpe",
                )
            },
        )

    async def async_step_notifications(self, user_input=None):
        self._ensure_working_copy()
        if user_input is not None:
            self._working_options.update(dict(user_input))
            self._persist_working_state()
            return await self.async_step_notification_energy_settings()
        return self.async_show_form(
            step_id="notifications",
            data_schema=_notification_schema(
                self.hass, self._working_options, self._rooms()
            ),
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

