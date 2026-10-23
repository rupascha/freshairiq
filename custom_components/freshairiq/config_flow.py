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
from .actuator_control import DEFAULT_FAN_FOLLOW_UP_MIN, DEFAULT_FAN_MAX_RUNTIME_MIN, FAN_CONTROL_MODES, FAN_CONTROL_OFF
from .climate_sources import entity_ids
from .settings_contract import native_option_key
from .goals import SWITCHABLE_GOALS, normalise_disabled_goals
from .notifications import _all_notification_targets, _available_notification_targets, _send_targets
from .room_creation_trace import trace_room_creation, trace_room_creation_after_reload, validation_error_codes
from .validation import option_relationship_error

# The flows are split into the config_flow_* modules; every name that used to live here
# stays importable from this module.
from .config_flow_fields import _RUNTIME_LISTENER_OPTION_KEYS, _room_entity_ids, _RUNTIME_LISTENER_DATA_KEYS, _RESIDENT_PROFILE_STORAGE_KEY, _slug, _entity_list, _number_or_none, _safe_int, _required, _optional, _time_default, _number, _bounded, _choice, _LEGACY_LEVEL_LABELS, _LEGACY_LEVEL_LABELS_EN, _is_de, _flow_language, _txt, _level_label, _level_options, _PROFILE_LABELS_DE, _HEATING_LABELS_DE, _PROFILE_LABELS_EN, _HEATING_LABELS_EN  # noqa: F401 - re-exported
from .config_flow_goals import _available_room_goals, _filter_room_priorities, GOAL_OFF, _shown_goal_priorities, _goal_priority_schema, _resolve_move_ranking, _resolve_goal_selection, _switched_off_goals, _ranked_goal_priorities, _goal_priority_errors  # noqa: F401 - re-exported
from .config_flow_schemas import _outdoor_configuration_error, _outdoor_schema  # noqa: F401 - re-exported
from .config_flow_fields import _CLIMATE_SENSOR_UNITS, _climate_sensor_selector  # noqa: F401 - re-exported
from .config_flow_fields import ClearableFormMixin
from .config_flow_rooms import _room_schema, _flatten_sections, _room_section_schema, _contact_reference_field, _contact_display_name, _single_contact_reference_schema, _schema_with_wizard_back  # noqa: F401 - re-exported
from .config_flow_rooms import _apply_single_contact_reference, _normalise_room, _normalise_room_control, _normalise_legacy_entry_data  # noqa: F401 - re-exported
from .config_flow_schemas import _model_schema, _cross_ventilation_schema, _profile_schema, _profile_details_schema, _building_schema, _resident_name_list, _resident_slot_overview, _resident_slot_placeholders, _resident_profiles_dict, _residents_schema, _forecast_schema, _air_quality_schema, _diagnostics_sharing_schema, _energy_system_schema, _energy_details_schema, _notification_schema  # noqa: F401 - re-exported
from .config_flow_subentry import FreshAirIQRoomSubentryFlow  # noqa: F401 - re-exported
from .config_flow_options import FreshAirIQOptionsFlow  # noqa: F401 - re-exported
from .config_flow_options_rooms import OptionsRoomsMixin
from .config_flow_options_settings import OptionsSettingsMixin


class FreshAirIQConfigFlow(ClearableFormMixin, config_entries.ConfigFlow, domain=DOMAIN):
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
                        CONF_OUTDOOR_PM25_ENTITY,
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


# 0.26.4.3: unexpected step exceptions are recorded (and, with consent, reported)
# instead of disappearing behind Home Assistant's "Unknown error occurred".
from .flow_errors import guard_flow_steps  # noqa: E402

guard_flow_steps(FreshAirIQConfigFlow, "config_flow")
guard_flow_steps(FreshAirIQRoomSubentryFlow, "room_flow")
guard_flow_steps(FreshAirIQOptionsFlow, "options_flow")
# The options steps are defined on the mixins; guard them where they live.
guard_flow_steps(OptionsRoomsMixin, "options_flow")
guard_flow_steps(OptionsSettingsMixin, "options_flow")

