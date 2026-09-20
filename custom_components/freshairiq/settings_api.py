"""Authenticated dashboard settings API for FreshAirIQ.

The dashboard editor and Home Assistant's config/options flow intentionally use
exactly the same ConfigEntry ``data`` and ``options``.  This module therefore
adds a modern presentation layer without introducing a second configuration
store.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .config_flow import _normalise_legacy_entry_data, _normalise_room
from .runtime import get_runtime_coordinator
from .typing import FreshAirIQConfigEntry
from .validation import option_relationship_message_de
from .const import (
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_COVERS,
    CONF_CONTACT_MODE,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_LEVELS,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOMS,
    DEFAULT_OPTIONS,
    DOMAIN,
    MOISTURE_SOURCES,
    ORIENTATIONS,
    CONTACT_MODE_ANY,
    CONTACT_MODE_ALL,
    PROFILE_COMFORT,
    PROFILE_DEHUMIDIFY,
    PROFILE_SUMMER_COOLING,
    PROPERTY_TYPES,
    HEATING_HEAT_PUMP,
    HEATING_GAS,
    HEATING_DISTRICT,
    HEATING_ELECTRIC,
    HEATING_OIL,
    NOTIFY_SCOPE_ROOM,
    NOTIFY_SCOPE_HOUSE,
    NOTIFY_SCOPE_BOTH,
    VERSION,
)

# Only settings that are also exposed by the native Devices & Services options
# flow are writable here. Internal model priors remain internal.
EDITABLE_OPTION_KEYS = {
    # model
    "start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh",
    "close_delta", "threshold_mode", "min_potential_percent_total_water",
    "min_potential_total_ml", "min_potential_room_ml", "min_duration_min",
    "max_duration_min", "post_ventilation_stabilization_min",
    "repeat_recommendation_cooldown_min", "repeat_min_benefit_ml",
    "min_return_next_5_min_ml", "max_temp_loss_next_5_min_c",
    "min_efficiency_ml_per_01c", "surface_factor", "mould_warn_surface_rh",
    "mould_critical_surface_rh", "co2_warn", "co2_critical",
    "learning_enabled", "learning_max_duration_min",
    # cross ventilation / profile / forecast / air quality
    "cross_ventilation_pairs", "cross_zone_connections", "operating_profile",
    "personalisation_enabled", "thermal_preference", "personal_priority",
    "night_window_preference",
    "cooling_start_temp_c", "cooling_min_outdoor_delta_c",
    "cooling_max_indoor_rh", "cooling_max_moisture_gain_5min_ml",
    "forecast_horizon_min", "pollen_enabled", "pollen_max",
    "pollen_strict_veto", "wind_orientation_enabled",
    "voc_sensor_enabled", "pm25_sensor_enabled", "illuminance_sensor_enabled",
    "voc_warn", "voc_critical", "pm25_warn", "pm25_critical",
    "humidify_below_rh", "shade_above_temp_c", "shade_min_illuminance_lx",
    # household / presence
    "property_type", "adult_occupants", "child_occupants",
    "adult_presence_entities", "child_presence_entities",
    "adult_resident_names", "child_resident_names", "resident_room_profiles",
    "presence_sensor_entities", "pet_safe_presence_entities",
    "pets_in_household", "untracked_follow_household",
    "night_start_hour", "night_end_hour", "night_forecast_enabled",
    # energy
    "heating_system", "electricity_price_per_kwh", "heat_pump_cop",
    "gas_price_per_kwh", "gas_efficiency", "district_price_per_kwh",
    "district_efficiency", "oil_price_per_liter", "oil_kwh_per_liter",
    "oil_efficiency",
    # notifications
    "notifications_enabled", "notification_targets", "notification_scope",
    "notification_room_keys", "notify_ventilate", "notify_close",
    "notify_complete", "notify_cooling", "notify_mould", "notify_sensor",
    "notify_night", "notify_learning", "notification_cooldown_min",
    # statistics / optional diagnostics sharing
    "statistics_days", "diagnostics_reporting_mode", "diagnostics_include_client_context",
}

_ENUMS: dict[str, set[str]] = {
    "threshold_mode": {"adaptive_home_size", "percent_total_water", "fixed_ml"},
    "operating_profile": {PROFILE_DEHUMIDIFY, PROFILE_COMFORT, PROFILE_SUMMER_COOLING},
    "thermal_preference": {"warm", "balanced", "cool"},
    "personal_priority": {"climate", "balanced", "energy"},
    "night_window_preference": {"automatic", "closed", "allowed"},
    "property_type": set(PROPERTY_TYPES),
    "heating_system": {HEATING_HEAT_PUMP, HEATING_GAS, HEATING_DISTRICT, HEATING_ELECTRIC, HEATING_OIL},
    "notification_scope": {NOTIFY_SCOPE_ROOM, NOTIFY_SCOPE_HOUSE, NOTIFY_SCOPE_BOTH},
    "diagnostics_reporting_mode": {"off", "errors", "daily", "weekly"},
}

# Same effective bounds as the native options flow. Keeping these constraints
# server-side prevents a hand-edited dashboard request from bypassing the UI.
_BOUNDS: dict[str, tuple[float, float]] = {
    "start_rh": (40, 90), "high_rh": (45, 95), "target_rh": (35, 75),
    "min_delta": (.1, 8), "min_delta_high_rh": (.1, 5), "close_delta": (-1, 3),
    "min_potential_percent_total_water": (1, 30), "min_potential_total_ml": (50, 5000),
    "min_potential_room_ml": (10, 1000), "min_duration_min": (1, 30),
    "max_duration_min": (3, 90), "post_ventilation_stabilization_min": (1, 15),
    "repeat_recommendation_cooldown_min": (5, 120), "repeat_min_benefit_ml": (10, 1000),
    "min_return_next_5_min_ml": (0, 500), "max_temp_loss_next_5_min_c": (.1, 5),
    "min_efficiency_ml_per_01c": (0, 200), "surface_factor": (.05, .8),
    "mould_warn_surface_rh": (60, 95), "mould_critical_surface_rh": (70, 100),
    "co2_warn": (600, 2500), "co2_critical": (800, 4000),
    "learning_max_duration_min": (15, 240), "cooling_start_temp_c": (18, 35),
    "cooling_min_outdoor_delta_c": (.5, 10), "cooling_max_indoor_rh": (40, 90),
    "cooling_max_moisture_gain_5min_ml": (0, 500), "forecast_horizon_min": (1, 120),
    "pollen_max": (0, 10), "voc_warn": (50, 5000), "voc_critical": (100, 10000),
    "pm25_warn": (1, 250), "pm25_critical": (2, 500), "humidify_below_rh": (20, 50),
    "shade_above_temp_c": (18, 35), "shade_min_illuminance_lx": (0, 100000),
    "adult_occupants": (0, 20), "child_occupants": (0, 20),
    "electricity_price_per_kwh": (0, 5), "heat_pump_cop": (1, 10),
    "gas_price_per_kwh": (0, 2), "gas_efficiency": (.5, 1),
    "district_price_per_kwh": (0, 5), "district_efficiency": (.5, 1),
    "oil_price_per_liter": (0, 5), "oil_kwh_per_liter": (8, 12), "oil_efficiency": (.5, 1),
    "notification_cooldown_min": (10, 1440), "statistics_days": (1, 365),
}

_BOOL_KEYS = {key for key, value in DEFAULT_OPTIONS.items() if isinstance(value, bool)}
_LIST_KEYS = {
    "adult_presence_entities", "child_presence_entities", "presence_sensor_entities",
    "pet_safe_presence_entities", "notification_targets", "notification_room_keys",
}
_INT_KEYS = {"adult_occupants", "child_occupants", "forecast_horizon_min", "statistics_days", "notification_cooldown_min"}
_DATA_KEYS = {CONF_OUTDOOR_WEATHER, CONF_OUTDOOR_TEMPERATURE, CONF_OUTDOOR_HUMIDITY, CONF_POLLEN_ENTITY}

# Option changes are runtime-safe because the coordinator reads ConfigEntry
# options on every update. Only the presence entity lists alter which Home
# Assistant states are subscribed for immediate refreshes, so those changes
# rebuild the lightweight listener set without unloading the integration.
_LISTENER_OPTION_KEYS = {
    "adult_presence_entities",
    "child_presence_entities",
    "presence_sensor_entities",
    "pet_safe_presence_entities",
    "voc_sensor_enabled",
    "pm25_sensor_enabled",
    "illuminance_sensor_enabled",
}


def _outdoor_configuration_valid_or_empty(data: dict[str, Any]) -> bool:
    """Allow deferred setup while rejecting an incomplete manual sensor pair."""
    if data.get(CONF_OUTDOOR_WEATHER):
        return True
    has_temperature = bool(data.get(CONF_OUTDOOR_TEMPERATURE))
    has_humidity = bool(data.get(CONF_OUTDOOR_HUMIDITY))
    return has_temperature == has_humidity


def _admin(request: web.Request) -> bool:
    user = request.get("hass_user")
    return bool(user and getattr(user, "is_admin", False))


def _coerce_option(key: str, value: Any) -> Any:
    if key not in EDITABLE_OPTION_KEYS:
        raise ValueError(f"Unbekannte Einstellung: {key}")
    if key in _ENUMS:
        value = str(value)
        if value not in _ENUMS[key]:
            raise ValueError(f"Ungültiger Wert für {key}")
        return value
    if key in _BOOL_KEYS:
        if isinstance(value, bool):
            return value
        if value in (0, 1, "0", "1", "true", "false", "on", "off"):
            return str(value).lower() in ("1", "true", "on")
        raise ValueError(f"{key} erwartet an/aus")
    if key in _LIST_KEYS:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"{key} erwartet eine Liste")
        return [str(item) for item in value if str(item).strip()]
    if key in ("night_start_hour", "night_end_hour"):
        text = str(value or "")
        if not re_time(text):
            raise ValueError("Zeit muss im Format HH:MM angegeben werden")
        return text
    if key in ("cross_ventilation_pairs", "cross_zone_connections"):
        return str(value or "")
    if key == "resident_room_profiles":
        text = str(value or "{}")
        if len(text) > 20000:
            raise ValueError("Bewohnerprofile sind zu groß")
        try:
            raw = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError) as err:
            raise ValueError("Bewohnerprofile enthalten ungültige Daten") from err
        if not isinstance(raw, dict):
            raise ValueError("Bewohnerprofile müssen ein Objekt sein")
        clean: dict[str, dict[str, Any]] = {}
        for slot, profile in raw.items():
            slot = str(slot or "")
            if not (slot.startswith("adult:") or slot.startswith("child:")) or not isinstance(profile, dict):
                continue
            thermal = str(profile.get("thermal_preference") or "inherit")
            if thermal not in {"inherit", "warm", "balanced", "cool"}:
                thermal = "inherit"
            rooms: list[str] = []
            for room in profile.get("room_keys") or []:
                key_text = str(room or "").strip()
                if key_text and key_text not in rooms:
                    rooms.append(key_text[:80])
            name = " ".join(str(profile.get("name") or "").strip().split())[:48]
            targets: list[str] = []
            for target in profile.get("notification_targets") or []:
                text = str(target or "").strip()
                if text and text not in targets:
                    targets.append(text[:120])
            clean[slot[:40]] = {"name": name, "room_keys": rooms[:50], "thermal_preference": thermal, "notification_targets": targets[:10]}
        return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    if key in _BOUNDS:
        try:
            number = float(value)
        except (TypeError, ValueError) as err:
            raise ValueError(f"{key} erwartet eine Zahl") from err
        lo, hi = _BOUNDS[key]
        if not lo <= number <= hi:
            raise ValueError(f"{key} muss zwischen {lo} und {hi} liegen")
        return int(round(number)) if key in _INT_KEYS else number
    # Remaining editable values are strings.
    return str(value)


async def _apply_runtime_update(
    hass: HomeAssistant,
    entry: FreshAirIQConfigEntry,
    *,
    rebuild_listeners: bool = False,
    invalidate_weather_cache: bool = False,
    trigger_diagnostics_check: bool = False,
) -> None:
    """Apply a non-structural ConfigEntry change without a full HA reload.

    FreshAirIQ's coordinator reads ``entry.data`` and ``entry.options`` live.
    Therefore scalar/model/profile/energy/notification changes only need a
    coordinator refresh. Source-entity changes additionally rebuild the tracked
    state listeners. If the integration is currently unloaded, the persisted
    ConfigEntry is already sufficient for the next setup and no reload is needed.
    """
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return

    async def _refresh_runtime() -> None:
        if rebuild_listeners:
            await coordinator.async_rebuild_listeners(
                invalidate_weather_cache=invalidate_weather_cache
            )
        await coordinator.async_request_refresh()
        if trigger_diagnostics_check:
            coordinator.telemetry.request_check()

    # Do not keep the settings HTTP request open while the full FreshAirIQ
    # calculation pipeline refreshes. The ConfigEntry is already persisted, so
    # the UI can acknowledge the write immediately while recomputation happens
    # in Home Assistant's event loop.
    hass.async_create_task(_refresh_runtime())


def re_time(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 2:
        return False
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _normalise_dashboard_room(raw: dict[str, Any], rooms: list[dict[str, Any]], keep_key: str | None = None) -> dict[str, Any]:
    raw = deepcopy(raw)
    include = bool(raw.get(CONF_ROOM_INCLUDE_CALCULATIONS, True))
    if include and not raw.get(CONF_ROOM_TEMPERATURE):
        raise ValueError("Temperatursensor fehlt")
    if include and not raw.get(CONF_ROOM_HUMIDITY):
        raise ValueError("Luftfeuchtigkeitssensor fehlt")
    contact_mode = str(raw.get(CONF_CONTACT_MODE, CONTACT_MODE_ANY))
    if contact_mode not in (CONTACT_MODE_ANY, CONTACT_MODE_ALL):
        raise ValueError("Ungültiger Kontaktmodus")
    raw[CONF_CONTACT_MODE] = contact_mode

    requested_delays = raw.get(CONF_CONTACT_DELAYS) or {}
    requested_orientations = raw.get(CONF_CONTACT_ORIENTATIONS) or {}
    requested_ref_temperatures = raw.get(CONF_CONTACT_REFERENCE_TEMPERATURES) or {}
    requested_ref_humidities = raw.get(CONF_CONTACT_REFERENCE_HUMIDITIES) or {}
    requested_contact_covers = raw.get(CONF_CONTACT_COVERS) or {}
    room, errors = _normalise_room(raw, rooms, keep_key=keep_key)
    if errors or room is None:
        first = next(iter(errors.values()), "Raumdaten sind unvollständig")
        messages = {
            "ventilation_contact_required": "Mindestens ein Fenster-/Türkontakt ist erforderlich.",
            "room_volume_required": "Raumvolumen oder vollständige Raummaße fehlen.",
            "room_volume_too_small": "Das berechnete Raumvolumen ist zu klein.",
            "room_name_required": "Der Raumname fehlt.",
        }
        raise ValueError(messages.get(first, first))

    contacts = list(room.get(CONF_ROOM_CONTACTS) or [])
    room[CONF_CONTACT_DELAYS] = {
        contact: max(0, min(600, int(float(requested_delays.get(contact, room.get(CONF_CONTACT_DELAYS, {}).get(contact, 0)) or 0))))
        for contact in contacts
    }
    room[CONF_CONTACT_ORIENTATIONS] = {
        contact: (
            str(requested_orientations.get(contact, room.get(CONF_CONTACT_ORIENTATIONS, {}).get(contact, "unknown")))
            if str(requested_orientations.get(contact, room.get(CONF_CONTACT_ORIENTATIONS, {}).get(contact, "unknown"))) in ORIENTATIONS
            else "unknown"
        )
        for contact in contacts
    }
    room[CONF_CONTACT_REFERENCE_TEMPERATURES] = {
        contact: str(requested_ref_temperatures.get(contact) or "").strip()
        for contact in contacts if str(requested_ref_temperatures.get(contact) or "").strip()
    }
    room[CONF_CONTACT_REFERENCE_HUMIDITIES] = {
        contact: str(requested_ref_humidities.get(contact) or "").strip()
        for contact in contacts if str(requested_ref_humidities.get(contact) or "").strip()
    }
    room[CONF_CONTACT_COVERS] = {
        contact: list(dict.fromkeys(
            str(entity_id) for entity_id in (requested_contact_covers.get(contact) or [])
            if str(entity_id).startswith("cover.")
        ))
        for contact in contacts if requested_contact_covers.get(contact)
    }
    for contact in contacts:
        has_temp = contact in room[CONF_CONTACT_REFERENCE_TEMPERATURES]
        has_humidity = contact in room[CONF_CONTACT_REFERENCE_HUMIDITIES]
        if has_temp != has_humidity:
            raise ValueError("Eine abweichende Referenz für ein Fenster/eine Tür benötigt immer Temperatur und Luftfeuchtigkeit aus demselben Luftbereich.")
    raw_sources = room.get("moisture_sources") or []
    room["moisture_sources"] = [source for source in raw_sources if source in MOISTURE_SOURCES]
    return room


def _sorted_rooms(rooms: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Return the canonical room order and tolerate legacy/corrupt sort values."""
    indexed = list(enumerate(list(rooms or [])))

    def _sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, str]:
        index, room = item
        try:
            order = int(room.get(CONF_ROOM_SORT_ORDER, index))
        except (TypeError, ValueError, OverflowError):
            order = index
        return order, index, str(room.get(CONF_ROOM_NAME, room.get("key", ""))).casefold()

    indexed.sort(key=_sort_key)
    return [room for _idx, room in indexed]


def _entry_payload(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> dict[str, Any]:
    data = _normalise_legacy_entry_data(dict(entry.data))
    data[CONF_ROOMS] = _sorted_rooms(list(data.get(CONF_ROOMS, [])))
    options = {**DEFAULT_OPTIONS, **dict(entry.options)}
    notify_services = sorted((hass.services.async_services().get("notify") or {}).keys())
    return {
        "version": VERSION,
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": data,
        "options": {key: options.get(key) for key in sorted(EDITABLE_OPTION_KEYS)},
        "defaults": {key: DEFAULT_OPTIONS.get(key) for key in sorted(EDITABLE_OPTION_KEYS)},
        "notify_services": notify_services,
    }


def _sync_room_subentries(hass: HomeAssistant, entry: FreshAirIQConfigEntry, rooms: list[dict[str, Any]]) -> None:
    """Mirror canonical room data into native Devices & Services subentries."""
    by_unique = {
        sub.unique_id: sub
        for sub in entry.subentries.values()
        if sub.subentry_type == "room"
    }
    room_keys = {str(room.get("key")) for room in rooms}
    for unique_id, subentry in list(by_unique.items()):
        key = str(unique_id or "").removeprefix("room:")
        if key not in room_keys and hasattr(hass.config_entries, "async_remove_subentry"):
            hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)
    for room in rooms:
        unique_id = f"room:{room['key']}"
        existing = by_unique.get(unique_id)
        if existing is not None:
            hass.config_entries.async_update_subentry(
                entry, existing, data=dict(room), title=room.get(CONF_ROOM_NAME, room["key"])
            )
        elif hasattr(hass.config_entries, "async_add_subentry"):
            from types import MappingProxyType
            from homeassistant import config_entries
            hass.config_entries.async_add_subentry(
                entry,
                config_entries.ConfigSubentry(
                    data=MappingProxyType(dict(room)),
                    subentry_type="room",
                    title=room.get(CONF_ROOM_NAME, room["key"]),
                    unique_id=unique_id,
                ),
            )


class FreshAirIQSettingsView(HomeAssistantView):
    """Read/write the existing FreshAirIQ ConfigEntry from the dashboard."""

    url = "/api/freshairiq/settings/{entry_id}"
    name = "api:freshairiq:settings"
    requires_auth = True

    def _entry(self, hass: HomeAssistant, entry_id: str) -> FreshAirIQConfigEntry | None:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return None
        return entry

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if not _admin(request):
            return self.json({"error": "Nur Home-Assistant-Administratoren dürfen FreshAirIQ konfigurieren."}, status_code=403)
        entry = self._entry(hass, entry_id)
        if entry is None:
            return self.json({"error": "FreshAirIQ-Konfiguration nicht gefunden."}, status_code=404)
        return self.json(_entry_payload(hass, entry))

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if not _admin(request):
            return self.json({"error": "Nur Home-Assistant-Administratoren dürfen FreshAirIQ konfigurieren."}, status_code=403)
        entry = self._entry(hass, entry_id)
        if entry is None:
            return self.json({"error": "FreshAirIQ-Konfiguration nicht gefunden."}, status_code=404)
        try:
            payload = await request.json()
            action = str(payload.get("action") or "update")
            if action == "set_option":
                key = str(payload.get("key") or "")
                value = _coerce_option(key, payload.get("value"))
                options = dict(entry.options)
                options[key] = value
                relation_error = option_relationship_message_de({**DEFAULT_OPTIONS, **options})
                if relation_error:
                    raise ValueError(relation_error)
                hass.config_entries.async_update_entry(entry, options=options)
                await _apply_runtime_update(
                    hass,
                    entry,
                    rebuild_listeners=key in _LISTENER_OPTION_KEYS,
                    trigger_diagnostics_check=key == "diagnostics_reporting_mode",
                )
            elif action == "set_data":
                key = str(payload.get("key") or "")
                if key not in _DATA_KEYS:
                    raise ValueError("Diese Basiseinstellung darf hier nicht geändert werden.")
                data = _normalise_legacy_entry_data(dict(entry.data))
                value = payload.get("value")
                if value in (None, ""):
                    data.pop(key, None)
                else:
                    data[key] = str(value)
                if not _outdoor_configuration_valid_or_empty(data):
                    raise ValueError("Außen-Temperatur und Außen-Luftfeuchtigkeit müssen gemeinsam gesetzt oder gemeinsam leer gelassen werden.")
                hass.config_entries.async_update_entry(entry, data=data)
                await _apply_runtime_update(
                    hass,
                    entry,
                    rebuild_listeners=True,
                    invalidate_weather_cache=key == CONF_OUTDOOR_WEATHER,
                )
            elif action == "set_levels":
                raw_levels = payload.get("levels")
                if not isinstance(raw_levels, list):
                    raise ValueError("Stockwerke/Bereiche müssen als Liste übertragen werden.")
                levels = []
                for item in raw_levels:
                    name = str(item or "").strip()
                    if name and name not in levels:
                        levels.append(name)
                data = _normalise_legacy_entry_data(dict(entry.data))
                used = {str(room.get(CONF_ROOM_FLOOR) or "") for room in data.get(CONF_ROOMS, []) if room.get(CONF_ROOM_FLOOR)}
                missing = sorted(used - set(levels))
                if missing:
                    raise ValueError("Diese Bereiche werden noch von Räumen verwendet: " + ", ".join(missing))
                data[CONF_LEVELS] = levels
                hass.config_entries.async_update_entry(entry, data=data)
                await _apply_runtime_update(hass, entry)
            elif action == "upsert_room":
                raw = payload.get("room")
                if not isinstance(raw, dict):
                    raise ValueError("Raumdaten fehlen.")
                data = _normalise_legacy_entry_data(dict(entry.data))
                rooms = list(data.get(CONF_ROOMS, []))
                keep_key = str(raw.get("key") or "").strip() or None
                if keep_key and not any(room.get("key") == keep_key for room in rooms):
                    raise ValueError("Der zu bearbeitende Raum wurde nicht gefunden.")
                normalised = _normalise_dashboard_room(raw, rooms, keep_key=keep_key)
                if keep_key:
                    index = next(i for i, room in enumerate(rooms) if room.get("key") == keep_key)
                    normalised[CONF_ROOM_SORT_ORDER] = int(rooms[index].get(CONF_ROOM_SORT_ORDER, index))
                    rooms[index] = normalised
                else:
                    normalised[CONF_ROOM_SORT_ORDER] = len(rooms)
                    rooms.append(normalised)
                floor = str(normalised.get(CONF_ROOM_FLOOR) or "").strip()
                levels = list(data.get(CONF_LEVELS, []))
                if floor and floor not in levels:
                    levels.append(floor)
                data[CONF_LEVELS] = levels
                data[CONF_ROOMS] = _sorted_rooms(rooms)
                hass.config_entries.async_update_entry(entry, data=data)
                _sync_room_subentries(hass, entry, data[CONF_ROOMS])
                hass.config_entries.async_schedule_reload(entry.entry_id)
            elif action == "delete_room":
                room_key = str(payload.get("room_key") or "")
                data = _normalise_legacy_entry_data(dict(entry.data))
                rooms = [room for room in data.get(CONF_ROOMS, []) if room.get("key") != room_key]
                if len(rooms) == len(data.get(CONF_ROOMS, [])):
                    raise ValueError("Raum wurde nicht gefunden.")
                for index, room in enumerate(rooms):
                    room[CONF_ROOM_SORT_ORDER] = index
                data[CONF_ROOMS] = rooms
                hass.config_entries.async_update_entry(entry, data=data)
                _sync_room_subentries(hass, entry, rooms)
                hass.config_entries.async_schedule_reload(entry.entry_id)
            elif action == "reorder_rooms":
                order = payload.get("order")
                if not isinstance(order, list):
                    raise ValueError("Raumreihenfolge fehlt.")
                data = _normalise_legacy_entry_data(dict(entry.data))
                rooms = list(data.get(CONF_ROOMS, []))
                by_key = {str(room.get("key")): room for room in rooms}
                if set(map(str, order)) != set(by_key):
                    raise ValueError("Raumreihenfolge ist unvollständig.")
                sorted_rooms = [by_key[str(key)] for key in order]
                for index, room in enumerate(sorted_rooms):
                    room[CONF_ROOM_SORT_ORDER] = index
                data[CONF_ROOMS] = sorted_rooms
                hass.config_entries.async_update_entry(entry, data=data)
                # Keep native room subentries in sync even though this is a
                # presentation-only change and does not require a full reload.
                by_unique = {
                    sub.unique_id: sub
                    for sub in entry.subentries.values()
                    if sub.subentry_type == "room"
                }
                for room in sorted_rooms:
                    subentry = by_unique.get(f"room:{room['key']}")
                    if subentry is not None and dict(subentry.data) != dict(room):
                        hass.config_entries.async_update_subentry(
                            entry,
                            subentry,
                            data=dict(room),
                            title=room.get(CONF_ROOM_NAME, room["key"]),
                        )
                # Reordering changes presentation/runtime ordering only. It does
                # not add/remove entities and therefore does not need a config
                # entry reload.
                await _apply_runtime_update(hass, entry)
            elif action == "reset_defaults":
                hass.config_entries.async_update_entry(entry, options=deepcopy(DEFAULT_OPTIONS))
                await _apply_runtime_update(hass, entry, rebuild_listeners=True)
            elif action == "reset_learning":
                coordinator = getattr(entry, "runtime_data", None)
                if coordinator is None:
                    raise ValueError("FreshAirIQ ist gerade nicht geladen.")
                await coordinator.store.async_reset_learning()
                await coordinator.async_request_refresh()
            else:
                raise ValueError("Unbekannte Einstellungsaktion.")
        except ValueError as err:
            return self.json({"error": str(err)}, status_code=400)
        except Exception as err:  # Keep frontend error reporting useful without leaking traceback.
            return self.json({"error": f"Einstellung konnte nicht gespeichert werden: {err}"}, status_code=500)

        # Return the canonical state after each write. The frontend can update its
        # controls immediately after either the lightweight runtime refresh or a
        # structural config-entry reload.
        return self.json({"ok": True, **_entry_payload(hass, entry)})


class FreshAirIQFeedbackView(HomeAssistantView):
    """Authenticated proxy for explicit user feedback; no Hub credential reaches the browser."""
    url = "/api/freshairiq/feedback/{entry_id}"
    name = "api:freshairiq:feedback"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return self.json({"error":"FreshAirIQ-Konfiguration nicht gefunden."}, status_code=404)
        try:
            payload = await request.json()
            kind = str(payload.get("type") or "").strip()
            message = str(payload.get("message") or "").strip()
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None:
                raise ValueError("FreshAirIQ ist gerade nicht geladen.")
            client_context = payload.get("client_context") if isinstance(payload.get("client_context"), dict) else None
            result = await coordinator.telemetry.async_submit_feedback(kind, message, client_context=client_context)
            return self.json({"ok":True, **result})
        except ValueError as err:
            return self.json({"error":str(err)}, status_code=400)
        except Exception as err:
            return self.json({"error":f"Feedback konnte nicht an den Diagnose-Hub übertragen werden: {err}"}, status_code=502)
