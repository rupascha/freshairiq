"""Shared config-flow field helpers: value coercion, form markers and language labels."""
from __future__ import annotations

import re
import voluptuous as vol
from typing import Any

from homeassistant.helpers import selector

from .const import (
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25_ENTITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOMS,
    HEATING_DISTRICT,
    HEATING_ELECTRIC,
    HEATING_GAS,
    HEATING_HEAT_PUMP,
    HEATING_OIL,
    PROFILE_COMFORT,
    PROFILE_DEHUMIDIFY,
    PROFILE_SUMMER_COOLING,
)
from .settings_contract import native_option_key


_RUNTIME_LISTENER_OPTION_KEYS = {
    "adult_presence_entities",
    "child_presence_entities",
    "presence_sensor_entities",
    "pet_safe_presence_entities",
    "voc_sensor_enabled",
    "pm25_sensor_enabled",
    "illuminance_sensor_enabled",
}


def _room_entity_ids(data: dict[str, Any]) -> set[str]:
    """Every entity id referenced by the configured rooms (sensors, contacts, covers, fans …)."""
    found: set[str] = set()

    def _collect(value: Any) -> None:
        if isinstance(value, str):
            if "." in value and " " not in value:
                found.add(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                _collect(key)
                _collect(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                _collect(item)

    rooms = data.get(CONF_ROOMS, [])
    if isinstance(rooms, list):
        for room in rooms:
            _collect(room)
    return found


_RUNTIME_LISTENER_DATA_KEYS = {
    CONF_OUTDOOR_WEATHER,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_HUMIDITY,
    CONF_POLLEN_ENTITY,
    CONF_OUTDOOR_PM25_ENTITY,
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


def _clearable_empty(validator: Any) -> Any:
    """Empty value of a selector the user can clear, ``None`` for any other field."""
    multiple = bool(getattr(validator, "config", {}).get("multiple"))
    if isinstance(validator, (selector.EntitySelector, selector.TextSelector)):
        return [] if multiple else ""
    if isinstance(validator, selector.SelectSelector) and multiple:
        return []
    return None


class _ClearableFormSchema(vol.Schema):
    """Form schema in which an emptied optional selector really becomes empty.

    The frontend drops emptied fields from the submitted data. A voluptuous
    ``default`` would put the stored value back and a ``{**old, **new}`` merge
    would keep it, so a once selected sensor could never be removed again.
    Validated input therefore carries an explicit empty value for every
    clearable optional field the submission left out.
    """

    def __call__(self, data: Any) -> Any:
        validated = super().__call__(data)
        for key, validator in self.schema.items():
            empty = _clearable_empty(validator)
            if isinstance(key, vol.Optional) and empty is not None and key.schema not in validated:
                validated[key.schema] = empty
        return validated


def clearable_form_schema(schema: Any) -> Any:
    """Prefill clearable optional selectors via ``suggested_value`` instead of ``default``.

    Applied to every FreshAirIQ form (see ``ClearableFormMixin``), including
    nested sections, so no current or future form can resurrect a removed value.
    """
    from homeassistant.data_entry_flow import section

    if not isinstance(schema, vol.Schema) or not isinstance(schema.schema, dict):
        return schema
    fields: dict[Any, Any] = {}
    for key, validator in schema.schema.items():
        if isinstance(validator, section):
            validator = section(clearable_form_schema(validator.schema), dict(validator.options))
        elif isinstance(key, vol.Optional) and _clearable_empty(validator) is not None and key.default is not vol.UNDEFINED:
            description = dict(key.description or {})
            stored = key.default()
            if description.get("suggested_value") in (None, "") and stored not in (None, "", []):
                description["suggested_value"] = stored
            key = vol.Optional(key.schema, description=description or None)
        fields[key] = validator
    return _ClearableFormSchema(fields, extra=schema.extra)


class ClearableFormMixin:
    """Route every shown form through ``clearable_form_schema``."""

    def async_show_form(self, *, data_schema: Any = None, **kwargs: Any) -> Any:
        return super().async_show_form(data_schema=clearable_form_schema(data_schema), **kwargs)  # type: ignore[misc]


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


# 0.26.5.1 (A-27): template/MQTT climate sensors often carry a unit but no
# device class. The backend already reads them; the pickers now offer every
# sensor with the device class *or* a matching unit.
_CLIMATE_SENSOR_UNITS = {"temperature": ["°C", "°F", "K"], "humidity": ["%"]}


def _climate_sensor_selector(*, device_class: str, multiple: bool = False) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(
        filter=[
            {"domain": "sensor", "device_class": device_class},
            {"domain": "sensor", "unit_of_measurement": _CLIMATE_SENSOR_UNITS[device_class]},
        ],
        multiple=multiple,
    ))
