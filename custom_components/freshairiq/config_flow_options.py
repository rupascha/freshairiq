"""Options flow: main menu, working copy and persistence; the steps live in mixin modules."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25_ENTITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOMS,
    CONF_ROOM_NAME,
    CONF_ROOM_SORT_ORDER,
    DEFAULT_OPTIONS,
)
from .config_flow_fields import (
    ClearableFormMixin,
    _RUNTIME_LISTENER_DATA_KEYS,
    _RUNTIME_LISTENER_OPTION_KEYS,
    _room_entity_ids,
    _safe_int,
)
from .config_flow_rooms import _normalise_legacy_entry_data
from .live_settings import room_structure
from .config_flow_schemas import _outdoor_configuration_error, _outdoor_schema
from .config_flow_options_connections import OptionsConnectionsMixin
from .config_flow_options_rooms import OptionsRoomsMixin
from .config_flow_options_settings import OptionsSettingsMixin


class FreshAirIQOptionsFlow(ClearableFormMixin, OptionsSettingsMixin, OptionsRoomsMixin, OptionsConnectionsMixin, config_entries.OptionsFlowWithReload):
    def __init__(self) -> None:
        self._working_data = None; self._working_options = None; self._selected_room_key = None
        self._structural_reload_pending = False
        self._pending_data_keys: set[str] = set()
        self._pending_option_keys: set[str] = set()
        self._room_entities_pending = False
        self._ha_import_queue: list[dict[str, str]] = []

    def _entry_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return deepcopy(dict(self.config_entry.data)), deepcopy(dict(self.config_entry.options))

    def _ensure_working_copy(self) -> None:
        # 0.26.5.3: every page is saved on submit, so the working copy only differs
        # from the entry by what someone else saved meanwhile (another dialog, a
        # room sub-entry, an automation) – continue from that instead of
        # overwriting it with this dialog's older copy.
        snapshot = self._entry_snapshot()
        if getattr(self, "_working_base", None) not in (None, snapshot):
            self._working_data = self._working_options = None
        self._working_base = snapshot
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
            self._working_base = self._entry_snapshot()

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
        # Room structure changes still need a real config-entry reload because
        # HA platform entities are created per room during async_setup_entry.
        # The room wizard saves its pages with reload_entry=False; remember such
        # a structural change so the deferred reload at the end of the wizard
        # (or on finish) still happens although the room keys were already
        # written by then.
        old_room_keys = {str(room.get("key")) for room in old_data.get(CONF_ROOMS, [])}
        new_room_keys = {str(room.get("key")) for room in new_data.get(CONF_ROOMS, [])}
        changed_data_keys = {
            key for key in set(old_data) | set(new_data)
            if old_data.get(key) != new_data.get(key)
        }
        changed_option_keys = {
            key for key in set(old_options) | set(new_options)
            if old_options.get(key) != new_options.get(key)
        }
        room_entities_changed = _room_entity_ids(old_data) != _room_entity_ids(new_data)
        if not reload_entry:
            if old_room_keys != new_room_keys:
                self._structural_reload_pending = True
            # A-26: edits saved page by page (e.g. a contact added to an existing
            # room) must still reach the running coordinator when the wizard ends.
            self._pending_data_keys |= changed_data_keys
            self._pending_option_keys |= changed_option_keys
            self._room_entities_pending |= room_entities_changed
        elif changed or self._structural_reload_pending or self._pending_data_keys or self._pending_option_keys:
            changed_data_keys |= self._pending_data_keys
            changed_option_keys |= self._pending_option_keys
            room_entities_changed = room_entities_changed or self._room_entities_pending
            self._pending_data_keys = set()
            self._pending_option_keys = set()
            self._room_entities_pending = False
            # All other settings are consumed live by the coordinator and can be
            # applied without tearing down/recreating the complete integration.
            structural_change = old_room_keys != new_room_keys or self._structural_reload_pending
            # 0.26.5.3: the running integration already reloads itself for every saved
            # room change (live_settings); reload here only if that did not happen yet
            running = getattr(self.config_entry, "runtime_data", None)
            structural_change = structural_change and getattr(running, "_room_structure", None) != room_structure(new_data)
            self._structural_reload_pending = False
            if structural_change:
                self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            else:
                coordinator = getattr(self.config_entry, "runtime_data", None)
                if coordinator is not None:
                    # Room sensors/contacts are listened to per room (A-26).
                    rebuild_listeners = bool(
                        room_entities_changed
                        or changed_data_keys & _RUNTIME_LISTENER_DATA_KEYS
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
        self._working_base = self._entry_snapshot()
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
            menu_options=["outdoor", "building", "residents", "levels", "rooms", "open_connections", "back_to_main"],
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
                    CONF_OUTDOOR_PM25_ENTITY,
                ):
                    value = user_input.get(key)
                    if value in (None, "", []):
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
