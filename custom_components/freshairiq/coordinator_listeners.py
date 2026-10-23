"""Coordinator source listeners, refresh coalescing and the end-of-session measurement wait."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import (
    DOMAIN,
    CONF_CONTACT_REFERENCE_HUMIDITIES,
    CONF_CONTACT_REFERENCE_TEMPERATURES,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_PM25_ENTITY,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_OUTDOOR_WEATHER,
    CONF_POLLEN_ENTITY,
    CONF_ROOMS,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_CO2,
    CONF_ROOM_EXHAUST_FAN,
    CONF_ROOM_HUMIDITY,
    CONF_ROOM_ILLUMINANCE,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_PM25,
    CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY,
    CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE,
    CONF_ROOM_REFERENCE_HUMIDITY,
    CONF_ROOM_REFERENCE_TEMPERATURE,
    CONF_ROOM_TEMPERATURE,
    CONF_ROOM_VOC,
    SESSION_CLOSE_CONFIRM_SECONDS,
    SESSION_END_MEASUREMENT_WAIT_SECONDS,
)
from .climate_sources import entity_ids
from .live_settings import DIAGNOSTICS_OPTION_KEYS, changed_option_keys, optional_room_sensors, room_structure
from .coordinator_contacts import _contact_ids
from .coordinator_sources import _state_report_timestamp
from .measurement_frame import report_timestamp_after_boundary
from .opening_state import normalize_opening_state

_LOGGER = logging.getLogger(__package__ + ".coordinator")  # same logger as coordinator.py


class CoordinatorListenersMixin:
    """Coordinator source listeners, refresh coalescing and the end-of-session measurement wait."""

    hass: HomeAssistant  # provided by the coordinator

    def _required_source_groups(self) -> list[tuple[str, list[str]]]:
        """Return required source groups; redundant room sensors form one group."""
        groups: list[tuple[str, list[str]]] = []
        for key, entity_id in (
            ("outdoor_weather", self.entry.data.get(CONF_OUTDOOR_WEATHER)),
            ("outdoor_temperature", self.entry.data.get(CONF_OUTDOOR_TEMPERATURE)),
            ("outdoor_humidity", self.entry.data.get(CONF_OUTDOOR_HUMIDITY)),
        ):
            if entity_id:
                groups.append((key, [str(entity_id)]))
        rooms = self.entry.data.get(CONF_ROOMS, [])
        if isinstance(rooms, list):
            for index, room in enumerate(rooms):
                if not isinstance(room, dict) or not room.get(CONF_ROOM_INCLUDE_CALCULATIONS, True):
                    continue
                room_key = str(room.get("key") or index)
                for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):
                    ids = entity_ids(room.get(key))
                    if ids:
                        groups.append((f"room:{room_key}:{key}", ids))
        return groups

    def _log_required_source_availability(self) -> None:
        """Track loss per logical source group, tolerating redundant room sensors."""
        unavailable: set[str] = set()
        for group_key, entity_ids_group in self._required_source_groups():
            any_available = False
            for entity_id in entity_ids_group:
                state = self.hass.states.get(entity_id)
                if state is not None and str(state.state).lower() not in {"unknown", "unavailable", "none", ""}:
                    any_available = True
                    break
            if not any_available:
                unavailable.add(group_key)

        newly_unavailable = unavailable - self._unavailable_required_sources
        recovered = self._unavailable_required_sources - unavailable
        for group_key in sorted(newly_unavailable):
            _LOGGER.info("Required FreshAirIQ source group %s is unavailable", group_key)
        for group_key in sorted(recovered):
            _LOGGER.info("Required FreshAirIQ source group %s is available again", group_key)
        self._unavailable_required_sources = unavailable

    @callback
    def _async_fire_automation_events(self) -> None:
        """Coordinator listener: fire user-automation events from published data.

        Runs after every successful update with the localized payload, so
        Alexa/TTS texts match the Home Assistant language. Never raises.
        """
        try:
            if isinstance(self.data, dict):
                self.automation_events.process(self.data)
        except Exception:  # noqa: BLE001 - user automations are optional consumers
            _LOGGER.debug("Could not fire FreshAirIQ automation events", exc_info=True)

    async def async_start_listeners(self) -> None:
        await self.telemetry.async_start()
        add_listener = getattr(self, "async_add_listener", None)
        if self._unsub_automation_events is None and callable(add_listener):
            self._unsub_automation_events = add_listener(self._async_fire_automation_events)
        entities, self._contact_entities = self._source_entities()
        self._listened_sources = frozenset(entities)
        self.robustness.listener_sources = len(entities)
        self._unsub_state = (
            async_track_state_change_event(self.hass, list(entities), self._async_source_changed)
            if entities else None
        )

    async def async_sync_runtime_config(self) -> None:
        """Every saved change works at once – no Home Assistant restart (0.26.5.3).

        Called for every config-entry update, whichever editor wrote it. Before,
        sources added on a page of the room wizard were only listened to once
        the wizard was finished, the automatic cover control kept the room setup
        it saw at startup, and a new or renamed room got its entities only after
        a restart. See ``live_settings`` for what each kind of change needs.
        """
        if room_structure(self.entry.data) != self._room_structure or self._enable_configured_room_sensors():
            # entities/devices exist per room: reload (an open settings dialog stays open)
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
            return
        if frozenset(self._source_entities()[0]) != self._listened_sources:
            await self.async_rebuild_listeners()
        controller = getattr(self, "actuator_controller", None)
        if controller is not None:
            await controller.async_sync()
        options = dict(self.entry.options)
        if changed_option_keys(self._applied_options, options) & DIAGNOSTICS_OPTION_KEYS:
            self.telemetry.request_check()
        self._applied_options = options
        from .repairs import async_sync_missing_entity_issue  # repairs imports the entry type

        async_sync_missing_entity_issue(self.hass, self.entry)
        await self.async_request_refresh()

    def _enable_configured_room_sensors(self) -> bool:
        """Enable a room's shading / moisture-source sensor once the room uses it."""
        registry = er.async_get(self.hass)
        enabled = False
        for suffix, configured in optional_room_sensors(self.entry.data).items():
            entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{self.entry.entry_id}_{suffix}")
            entry = registry.async_get(entity_id) if entity_id else None
            if configured and entry is not None and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(entity_id, disabled_by=None)
                enabled = True
        return enabled

    def _source_entities(self) -> tuple[set[str], set[str]]:
        """All entities whose change triggers a refresh, and the opening contacts among them."""
        entities: set[str] = set()
        contacts: set[str] = set()
        for entity_id in (self.entry.data.get(CONF_OUTDOOR_WEATHER), self.entry.data.get(CONF_OUTDOOR_TEMPERATURE), self.entry.data.get(CONF_OUTDOOR_HUMIDITY)):
            if entity_id: entities.add(entity_id)
        entities.update(entity_ids(self.entry.data.get(CONF_POLLEN_ENTITY)))
        entities.update(entity_ids(self.entry.data.get(CONF_OUTDOOR_PM25_ENTITY)))
        options = self.options
        optional_sensor_keys = [
            (CONF_ROOM_VOC, bool(options.get("voc_sensor_enabled", True))),
            (CONF_ROOM_PM25, bool(options.get("pm25_sensor_enabled", True))),
            (CONF_ROOM_ILLUMINANCE, bool(options.get("illuminance_sensor_enabled", True))),
        ]
        for room in self.entry.data.get(CONF_ROOMS, []):
            for key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):
                entities.update(entity_ids(room.get(key)))
            for key in (CONF_ROOM_REFERENCE_TEMPERATURE, CONF_ROOM_REFERENCE_HUMIDITY, CONF_ROOM_EXHAUST_REFERENCE_TEMPERATURE,
                        CONF_ROOM_EXHAUST_REFERENCE_HUMIDITY, CONF_ROOM_CO2, CONF_ROOM_CLIMATE):
                if room.get(key): entities.add(str(room[key]))
            # exhaust_fan is legacy-scalar compatible but may now contain multiple
            # fan/switch entities (including separate hardware stage entities).
            entities.update(entity_ids(room.get(CONF_ROOM_EXHAUST_FAN)))
            for key, enabled in optional_sensor_keys:
                if enabled and room.get(key):
                    entities.add(room[key])
            # Opening-specific climate references are first-class data sources.
            # They already exist in the room configuration, so no extra user
            # setup is required; listening to them also makes a requested refresh
            # immediately visible to the coordinator.
            for mapping_key in (CONF_CONTACT_REFERENCE_TEMPERATURES, CONF_CONTACT_REFERENCE_HUMIDITIES):
                mapping = room.get(mapping_key) or {}
                if isinstance(mapping, dict):
                    entities.update(str(entity_id) for entity_id in mapping.values() if entity_id)
            room_contacts = set(_contact_ids(room))
            contacts.update(room_contacts)
            entities.update(room_contacts)
        # Presence changes should recalculate live and night forecasts immediately.
        for entity_id in (*options.get("adult_presence_entities", []), *options.get("child_presence_entities", []), *options.get("presence_sensor_entities", []), *options.get("pet_safe_presence_entities", [])):
            if entity_id: entities.add(str(entity_id))
        return entities, contacts

    def _clear_runtime_listeners(self) -> None:
        """Remove state/contact listeners without touching persisted learning data."""
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        for unsub in list(self._contact_confirm_unsubs.values()):
            unsub()
        self._contact_confirm_unsubs.clear()
        for unsub in list(self._final_measurement_unsubs.values()):
            unsub()
        self._final_measurement_unsubs.clear()
        if self._refresh_coalesce_unsub:
            self._refresh_coalesce_unsub()
            self._refresh_coalesce_unsub = None

    async def async_rebuild_listeners(self, *, invalidate_weather_cache: bool = False) -> None:
        """Rebuild source listeners after a live configuration change.

        This is intentionally lighter than unloading/reloading the complete config
        entry. Existing entities, learning state and platform registrations remain
        untouched; only the set of source entities that can trigger an immediate
        coordinator refresh is rebuilt from the updated ConfigEntry.

        When the configured weather entity changes, its hourly forecast cache must
        be cleared as well; otherwise a live source switch could temporarily keep
        using forecast rows fetched from the previous provider.
        """
        self._clear_runtime_listeners()
        if invalidate_weather_cache:
            self._hourly_forecast_cache = []
            self._hourly_forecast_fetched_at = None
            self._hourly_forecast_failures = 0
        await self.async_start_listeners()

    async def async_stop_listeners(self) -> None:
        self._clear_runtime_listeners()
        if self._unsub_automation_events is not None:
            self._unsub_automation_events()
            self._unsub_automation_events = None
        await self.telemetry.async_stop()
        # Flush the latest live balance before reload/shutdown.
        await self.store.async_save()

    def _room_climate_refresh_entities(
        self, cfg: dict[str, Any], *,
        active_reference_temperature: str | None = None,
        active_reference_humidity: str | None = None,
    ) -> list[str]:
        """Return already-configured climate entities for a best-effort refresh.

        No integration- or vendor-specific entity is invented here. The helper
        only reuses entities the user already assigned to FreshAirIQ.
        """
        candidates: set[str] = set()
        for entity_id in (
            *entity_ids(cfg.get(CONF_ROOM_TEMPERATURE)), *entity_ids(cfg.get(CONF_ROOM_HUMIDITY)),
            cfg.get(CONF_ROOM_REFERENCE_TEMPERATURE), cfg.get(CONF_ROOM_REFERENCE_HUMIDITY),
            active_reference_temperature, active_reference_humidity,
            self.entry.data.get(CONF_OUTDOOR_TEMPERATURE),
            self.entry.data.get(CONF_OUTDOOR_HUMIDITY),
            self.entry.data.get(CONF_OUTDOOR_WEATHER),
        ):
            if entity_id:
                candidates.add(str(entity_id))
        for mapping_key in (CONF_CONTACT_REFERENCE_TEMPERATURES, CONF_CONTACT_REFERENCE_HUMIDITIES):
            mapping = cfg.get(mapping_key) or {}
            if isinstance(mapping, dict):
                candidates.update(str(entity_id) for entity_id in mapping.values() if entity_id)
        # Avoid calling update_entity for IDs that are not currently known to HA.
        return sorted(entity_id for entity_id in candidates if self.hass.states.get(entity_id) is not None)

    async def _async_request_room_sensor_refresh(
        self, cfg: dict[str, Any], *,
        active_reference_temperature: str | None = None,
        active_reference_humidity: str | None = None,
    ) -> None:
        """Ask Home Assistant to update known room/reference climate entities.

        This is deliberately best-effort. Polling integrations may update at
        once; sleeping/push battery devices may ignore the request. Either way,
        FreshAirIQ continues safely and evaluates the reports it actually sees.
        """
        entities = self._room_climate_refresh_entities(
            cfg,
            active_reference_temperature=active_reference_temperature,
            active_reference_humidity=active_reference_humidity,
        )
        if not entities:
            return
        try:
            await self.hass.services.async_call(
                "homeassistant", "update_entity", {"entity_id": entities}, blocking=False
            )
        except Exception:  # noqa: BLE001 - refresh support differs by integration/device
            _LOGGER.debug("Best-effort climate refresh failed for room %s", cfg.get("key"), exc_info=True)

    def _cancel_final_measurement_timer(self, room_key: str) -> None:
        unsub = self._final_measurement_unsubs.pop(str(room_key), None)
        if unsub:
            unsub()

    def _schedule_final_measurement_timeout(self, room_key: str, delay_s: float) -> None:
        room_key = str(room_key)
        if room_key in self._final_measurement_unsubs:
            return

        @callback
        def _timeout(_now: Any, *, _room_key: str = room_key) -> None:
            self._final_measurement_unsubs.pop(_room_key, None)
            self.hass.async_create_task(self.async_request_refresh())

        self._final_measurement_unsubs[room_key] = async_call_later(
            self.hass, max(float(delay_s), 0.05), _timeout
        )

    def _clear_final_measurement_wait(self, mem: dict[str, Any], room_key: str) -> None:
        self._cancel_final_measurement_timer(room_key)
        mem["session_close_pending"] = False
        mem["session_close_detected_at"] = None
        mem["session_close_wait_started_at"] = None
        mem["session_close_deadline_at"] = None
        mem["session_close_temperature_baseline"] = None
        mem["session_close_humidity_baseline"] = None
        mem["session_close_temperature_feedback"] = False
        mem["session_close_humidity_feedback"] = False
        mem["session_close_refresh_requested_at"] = None

    def _begin_final_measurement_wait(
        self, mem: dict[str, Any], cfg: dict[str, Any], *,
        now: datetime, physical_closed_at: datetime,
        temperature_state: Any, humidity_state: Any,
        active_reference_temperature: str | None,
        active_reference_humidity: str | None,
    ) -> None:
        if mem.get("session_close_pending"):
            return
        mem["session_close_pending"] = True
        mem["session_close_detected_at"] = mem.get("session_close_detected_at") or physical_closed_at.isoformat()
        mem["session_close_wait_started_at"] = now.isoformat()
        deadline = now + timedelta(seconds=SESSION_END_MEASUREMENT_WAIT_SECONDS)
        mem["session_close_deadline_at"] = deadline.isoformat()
        mem["session_close_temperature_baseline"] = _state_report_timestamp(temperature_state)
        mem["session_close_humidity_baseline"] = _state_report_timestamp(humidity_state)
        mem["session_close_temperature_feedback"] = False
        mem["session_close_humidity_feedback"] = False
        mem["session_close_refresh_requested_at"] = now.isoformat()
        self._schedule_final_measurement_timeout(cfg["key"], SESSION_END_MEASUREMENT_WAIT_SECONDS)
        self.hass.async_create_task(self._async_request_room_sensor_refresh(
            cfg,
            active_reference_temperature=active_reference_temperature,
            active_reference_humidity=active_reference_humidity,
        ))

    @staticmethod
    def _update_final_measurement_feedback(
        mem: dict[str, Any], temperature_state: Any, humidity_state: Any,
    ) -> int:
        current_temp = _state_report_timestamp(temperature_state)
        current_humidity = _state_report_timestamp(humidity_state)
        close_boundary = mem.get("session_close_detected_at")
        # A report that arrived during the 3 s close-confirmation window is still
        # a valid *post-close* response. Compare against the physical contact-close
        # boundary as well as the later refresh baseline so it cannot be lost.
        if current_temp and (
            report_timestamp_after_boundary(current_temp, close_boundary)
            if close_boundary else current_temp != mem.get("session_close_temperature_baseline")
        ):
            mem["session_close_temperature_feedback"] = True
        if current_humidity and (
            report_timestamp_after_boundary(current_humidity, close_boundary)
            if close_boundary else current_humidity != mem.get("session_close_humidity_baseline")
        ):
            mem["session_close_humidity_feedback"] = True
        return int(bool(mem.get("session_close_temperature_feedback"))) + int(bool(mem.get("session_close_humidity_feedback")))

    @callback
    def _async_source_changed(self, event: Any) -> None:
        self.robustness.source_event()
        # Sensor/contact changes trigger an immediate refresh; the 30 s timer is only fallback.
        # A contact that reports closed gets one additional refresh after the
        # fixed 3 s confirmation window. If that same contact reopens first, its
        # pending callback is cancelled. This prevents a brief accidental close
        # from ending/overwriting a still-running ventilation session.
        entity_id = str((event.data or {}).get("entity_id") or "")
        if entity_id in self._contact_entities:
            previous = self._contact_confirm_unsubs.pop(entity_id, None)
            if previous:
                previous()
            new_state = (event.data or {}).get("new_state")
            # Always schedule a second evaluation after the fixed three-state
            # stability window. Binary contacts still react immediately because
            # they never enter explicit-three-state stabilisation; this callback
            # is only a harmless confirmation refresh for them. For an explicit
            # three-state contact it is what confirms closed/open/tilted even if
            # a sleeping battery device sends no further telegram. A newer state
            # event cancels and replaces this timer, so the newest candidate must
            # itself remain stable for the full window.
            if new_state is not None and normalize_opening_state(new_state.state) in {"closed", "open", "tilted"}:
                @callback
                def _confirm_contact_state(_now: Any, *, _entity_id: str = entity_id) -> None:
                    self._contact_confirm_unsubs.pop(_entity_id, None)
                    self.hass.async_create_task(self.async_request_refresh())

                self._contact_confirm_unsubs[entity_id] = async_call_later(
                    self.hass, SESSION_CLOSE_CONFIRM_SECONDS, _confirm_contact_state
                )
        # Coalesce bursts where a device reports temperature/humidity/contact
        # states a few milliseconds apart. The coordinator always reads the newest
        # HA state, so this reduces duplicate work without changing calculations.
        if self._refresh_coalesce_unsub is None:
            @callback
            def _coalesced_refresh(_now: Any) -> None:
                self._refresh_coalesce_unsub = None
                self.robustness.coalesced_refresh()
                self.hass.async_create_task(self.async_request_refresh())

            # Leading-edge debounce: one refresh is guaranteed after 120 ms even
            # when a chatty sensor keeps emitting state changes continuously.
            self._refresh_coalesce_unsub = async_call_later(self.hass, 0.12, _coalesced_refresh)
