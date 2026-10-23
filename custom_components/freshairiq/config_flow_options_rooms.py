"""Options-flow room steps: import from Home Assistant areas, add, edit, sort, openings and removal."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
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
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_WINDOW_ORIENTATION,
    ORIENTATIONS,
    ORIENTATION_UNKNOWN,
)
from .config_flow_fields import _flow_language, _number, _safe_int, _txt
from .config_flow_goals import (
    _available_room_goals,
    _goal_priority_errors,
    _goal_priority_schema,
    _ranked_goal_priorities,
    _resolve_move_ranking,
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


class OptionsRoomsMixin:
    """Options-flow room steps: import from Home Assistant areas, add, edit, sort, openings and removal."""

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
            trace_room_creation(self.hass, self.config_entry, source="options_flow", stage="validation_failed", outcome="rejected", extra={"validation_error_keys": sorted(map(str, errors)), "validation_error_codes": validation_error_codes(errors)})
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
                room[CONF_ROOM_GOAL_PRIORITIES], room[CONF_ROOM_DISABLED_GOALS] = (
                    _ranked_goal_priorities(user_input, room), _switched_off_goals(user_input, room)
                )
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
            if len(ranked_keys) != len(current_keys) or any(key not in current_keys for key in ranked_keys):
                return self.async_show_form(
                    step_id="sort_rooms",
                    data_schema=self._room_order_schema(rooms),
                    errors={"base": "invalid_room_order"},
                )
            # 0.26.4.6: choosing a room for a position moves it there; no need
            # to change two dropdowns to swap rooms.
            ranked_keys = _resolve_move_ranking(ranked_keys, current_keys)
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
            if room is not None:
                # End of the wizard for a contactless room: apply the deferred reload.
                self._persist_working_state(reload_entry=True)
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
