"""Room subentry flow: create and reconfigure one room as a config subentry."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    selector,
)

from .const import (
    CONF_CONTACT_DELAY,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_ORIENTATIONS,
    CONF_LEVELS,
    CONF_ROOMS,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_DISABLED_GOALS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_GOAL_PRIORITIES,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_WINDOW_ORIENTATION,
    ORIENTATIONS,
    ORIENTATION_UNKNOWN,
)
from .config_flow_fields import ClearableFormMixin, _flow_language, _number, _safe_int, _txt
from .config_flow_goals import (
    _available_room_goals,
    _goal_priority_errors,
    _goal_priority_schema,
    _ranked_goal_priorities,
    _switched_off_goals,
)
from .config_flow_rooms import (
    _apply_single_contact_reference,
    _contact_display_name,
    _normalise_room,
    _room_section_schema,
    _schema_with_wizard_back,
    _single_contact_reference_schema,
)
from .room_creation_trace import trace_room_creation, trace_room_creation_after_reload, validation_error_codes


class FreshAirIQRoomSubentryFlow(ClearableFormMixin, config_entries.ConfigSubentryFlow):
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
            trace_room_creation(self.hass, self._get_entry(), source="native_subentry", stage="validation_failed", outcome="rejected", extra={"validation_error_keys": sorted(map(str, errors)), "validation_error_codes": validation_error_codes(errors)})
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
                room[CONF_ROOM_GOAL_PRIORITIES], room[CONF_ROOM_DISABLED_GOALS] = (
                    _ranked_goal_priorities(user_input, room), _switched_off_goals(user_input, room)
                )
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
            # 0.26.5.2: automatic cover/fan control follows the edit at once
            controller = getattr(coordinator, "actuator_controller", None)
            if controller is not None:
                await controller.async_reload()

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
                room[CONF_ROOM_GOAL_PRIORITIES], room[CONF_ROOM_DISABLED_GOALS] = (
                    _ranked_goal_priorities(user_input, room), _switched_off_goals(user_input, room)
                )
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
