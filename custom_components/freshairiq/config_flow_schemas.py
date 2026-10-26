"""Settings forms of the options flow (model, profile, building, residents, air quality, energy, notifications)."""
from __future__ import annotations

import voluptuous as vol
from typing import Any

from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25_ENTITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOM_NAME,
    HEATING_DISTRICT,
    HEATING_ELECTRIC,
    HEATING_GAS,
    HEATING_HEAT_PUMP,
    HEATING_OIL,
    NOTIFY_SCOPE_BOTH,
    NOTIFY_SCOPE_HOUSE,
    NOTIFY_SCOPE_ROOM,
    PROFILE_COMFORT,
    PROFILE_DEHUMIDIFY,
    PROFILE_SUMMER_COOLING,
    PROPERTY_HOUSE,
    PROPERTY_TYPES,
)
from .climate_sources import entity_ids
from .config_flow_fields import _bounded, _climate_sensor_selector, _number, _optional, _time_default
from .notifications import _available_notification_targets
from .settings_contract import native_option_key


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
        _optional(CONF_OUTDOOR_TEMPERATURE, data.get(CONF_OUTDOOR_TEMPERATURE)): _climate_sensor_selector(device_class="temperature"),
        _optional(CONF_OUTDOOR_HUMIDITY, data.get(CONF_OUTDOOR_HUMIDITY)): _climate_sensor_selector(device_class="humidity"),
        # 0.26.4.6 (user feedback): several pollen sensors (e.g. one per pollen
        # type); the highest current value counts. Legacy single values stay valid.
        _optional(CONF_POLLEN_ENTITY, entity_ids(data.get(CONF_POLLEN_ENTITY)) or None): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        # 0.26.4.7 (user feedback): outdoor fine dust, e.g. Sensor.Community.
        # 0.26.5.2 (community: WAQI "sensor.heilbronn_germany_pm25" was not offered):
        # air-quality services often publish PM2.5 without the pm25 device class.
        _optional(CONF_OUTDOOR_PM25_ENTITY, entity_ids(data.get(CONF_OUTDOOR_PM25_ENTITY)) or None): selector.EntitySelector(
            selector.EntitySelectorConfig(filter=[
                {"domain": "sensor", "device_class": "pm25"},
                {"domain": "sensor", "unit_of_measurement": ["µg/m³", "μg/m³"]},
                {"domain": "sensor", "integration": "waqi"},
            ], multiple=True)
        ),
    })


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
    # 0.26.5.4: comfort – the lower limit for cooling advice; the return and
    # efficiency values of the comfort profile live on the model page.
    return vol.Schema({
        vol.Required(native_option_key("cooling_start_temp_c"), default=current.get("cooling_start_temp_c", 24.0)): _number(18, 35, 0.5, "°C"),
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
            vol.Required(native_option_key("presence_night_hold"), default=bool(current.get("presence_night_hold", False))): bool,
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
        vol.Required(native_option_key("outdoor_pm25_enabled"), default=bool(current.get("outdoor_pm25_enabled", True))): bool,
        vol.Required(native_option_key("outdoor_pm25_max"), default=_bounded(current.get("outdoor_pm25_max"), 35.0, 5, 500)): _number(5, 500, 1, "µg/m³"),
        vol.Required(native_option_key("wind_orientation_enabled"), default=bool(current.get("wind_orientation_enabled", True))): bool,
        vol.Required(native_option_key("voc_warn"), default=_bounded(current.get("voc_warn"), 600.0, 50, 5000)): _number(50, 5000, 50),
        vol.Required(native_option_key("voc_critical"), default=_bounded(current.get("voc_critical"), 1200.0, 100, 10000)): _number(100, 10000, 50),
        vol.Required(native_option_key("pm25_warn"), default=_bounded(current.get("pm25_warn"), 15.0, 1, 250)): _number(1, 250, 1, "µg/m³"),
        vol.Required(native_option_key("pm25_critical"), default=_bounded(current.get("pm25_critical"), 35.0, 2, 500)): _number(2, 500, 1, "µg/m³"),
        vol.Required(native_option_key("humidify_below_rh"), default=_bounded(current.get("humidify_below_rh"), 35.0, 20, 50)): _number(20, 50, 1, "%"),
        vol.Required(native_option_key("shade_above_temp_c"), default=_bounded(current.get("shade_above_temp_c"), 24.0, 18, 35)): _number(18, 35, 0.5, "°C"),
        vol.Required(native_option_key("shade_min_illuminance_lx"), default=_bounded(current.get("shade_min_illuminance_lx"), 10000.0, 0, 100000)): _number(0, 100000, 500, "lx"),
        vol.Required(native_option_key("shade_lead_min"), default=_bounded(current.get("shade_lead_min"), 15, 0, 60)): _number(0, 60, 5, "min"),
        vol.Required(native_option_key("shade_forecast_max_c"), default=_bounded(current.get("shade_forecast_max_c"), 25.0, 15, 40)): _number(15, 40, 0.5, "°C"),
        vol.Required(native_option_key("shade_max_cloud_coverage"), default=_bounded(current.get("shade_max_cloud_coverage"), 80.0, 0, 100)): _number(0, 100, 5, "%"),
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
        vol.Required(native_option_key("notify_status_messages"), default=bool(current.get("notify_status_messages", True))): bool,
        vol.Required(native_option_key("action_reminder_min"), default=_bounded(current.get("action_reminder_min"), 0, 0, 60)): _number(0, 60, 5, "min"),
        vol.Required(native_option_key("suppress_notifications_at_night"), default=bool(current.get("suppress_notifications_at_night", False))): bool,
        vol.Required(native_option_key("notify_only_when_home"), default=bool(current.get("notify_only_when_home", False))): bool,
        vol.Required(native_option_key("notify_important_when_away"), default=bool(current.get("notify_important_when_away", True))): bool,
        vol.Optional("test_notification_now", default=False): bool,
    })
