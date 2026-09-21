"""FreshAirIQ integration."""
from __future__ import annotations

from pathlib import Path
from functools import partial
from types import MappingProxyType
import logging

from homeassistant import config_entries

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_ID, CONF_TYPE, CONF_URL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    CONF_CONTACT_MODE,
    CONF_LEGACY_ENTRY_ID,
    CONF_LEVELS,
    CONF_ROOM_CONTACT,
    CONF_ROOM_CONTACTS,
    CONF_ROOM_HEIGHT,
    CONF_ROOM_NAME,
    CONF_ROOMS,
    CONF_ROOM_FLOOR,
    CONF_ROOM_INCLUDE_CALCULATIONS,
    CONF_ROOM_SORT_ORDER,
    CONF_ROOM_WINDOW_ORIENTATION,
    CONF_CONTACT_DELAYS,
    CONF_CONTACT_ORIENTATIONS,
    CONF_CONTACT_DELAY,
    FLOOR_GROUND,
    ORIENTATION_UNKNOWN,
    CONF_ROOM_LENGTH,
    CONF_ROOM_WIDTH,
    CONF_VOLUME_MODE,
    CONTACT_MODE_ANY,
    VOLUME_MODE_DIMENSIONS,
    VOLUME_MODE_DIRECT,
    DOMAIN,
    PLATFORMS,
    VERSION,
    DEFAULT_OPTIONS,
)
from .coordinator import FreshAirIQCoordinator
from .storage import LearningStore
from .diagnostics import FreshAirIQDiagnosticsView
from .settings_api import FreshAirIQSettingsView, FreshAirIQFeedbackView
from .validation import RELATION_OPTION_KEYS, repair_option_relationships
from .runtime import clear_runtime_coordinator, get_runtime_coordinator, iter_runtime_coordinators, set_runtime_coordinator
from .intervention import executable_intervention
from .repairs import async_clear_missing_entity_issue, async_sync_missing_entity_issue
from .typing import FreshAirIQConfigEntry


_LOGGER = logging.getLogger(__name__)

_FRONTEND_DIR = Path(__file__).parent / "frontend"
_FRONTEND_URL = "/freshairiq/frontend"
_FRONTEND_MODULE = f"{_FRONTEND_URL}/freshairiq-card.js?v={VERSION}"
_FRONTEND_MODULE_BASE = f"{_FRONTEND_URL}/freshairiq-card.js"
_FRONTEND_OLD_LOADER_BASE = f"{_FRONTEND_URL}/freshairiq-loader.js"


def _is_freshairiq_resource(url: object) -> bool:
    """Return whether a Lovelace resource points at the bundled FreshAirIQ card."""
    return isinstance(url, str) and url.split("?", 1)[0] in {
        _FRONTEND_MODULE_BASE, _FRONTEND_OLD_LOADER_BASE
    }


async def _async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Register the card once as a Lovelace module in storage mode.

    Return ``True`` only when the storage resource is active. Callers may then
    use ``add_extra_js_url`` strictly as a YAML/legacy/error fallback, never as
    a second concurrent loader for the same ES module.
    """
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.warning(
            "FreshAirIQ frontend fallback is active because Lovelace data is unavailable"
        )
        return False

    resource_mode = getattr(lovelace_data, "resource_mode", None)
    resources = getattr(lovelace_data, "resources", None)
    if resource_mode != MODE_STORAGE or not isinstance(resources, ResourceStorageCollection):
        _LOGGER.debug(
            "FreshAirIQ Lovelace resource is not auto-managed because resource mode is %s; "
            "the global frontend module fallback remains active",
            resource_mode,
        )
        return False

    try:
        # Explicitly force lazy loading before reading/creating items.  This keeps
        # compatibility with HA releases where Lovelace resources were lazy-loaded
        # and prevents an early create from replacing an existing resource store.
        await resources.async_get_info()
        matching = [
            item for item in resources.async_items()
            if _is_freshairiq_resource(item.get(CONF_URL))
        ]

        if matching:
            current = matching[0]
            updates: dict[str, str] = {}
            if current.get(CONF_URL) != _FRONTEND_MODULE:
                updates[CONF_URL] = _FRONTEND_MODULE
            if current.get(CONF_TYPE) != "module":
                updates["res_type"] = "module"
            if updates:
                await resources.async_update_item(current[CONF_ID], updates)
                _LOGGER.info("Updated FreshAirIQ Lovelace frontend resource to %s", VERSION)
            # 0.23.0.8 migration: older configuration-error hotfixes could leave
            # loader.js and/or duplicate FreshAirIQ resources in persistent
            # Lovelace storage. Keep exactly one direct card.js resource.
            for duplicate in matching[1:]:
                try:
                    await resources.async_delete_item(duplicate[CONF_ID])
                except Exception:  # noqa: BLE001 - cleanup must not break setup
                    _LOGGER.debug("Could not remove stale FreshAirIQ Lovelace resource", exc_info=True)
            return True

        await resources.async_create_item(
            {"res_type": "module", CONF_URL: _FRONTEND_MODULE}
        )
        _LOGGER.info("Registered FreshAirIQ Lovelace frontend resource %s", VERSION)
        return True
    except Exception:  # noqa: BLE001 - frontend registration must never break backend setup
        _LOGGER.exception(
            "Could not register the FreshAirIQ Lovelace resource; "
            "the global frontend module fallback remains active"
        )
        return False






async def _async_execute_intervention_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Execute one explicitly requested, precomputed FreshAirIQ intervention.

    FreshAirIQ never invokes this handler by itself.  The user or a Home
    Assistant automation must call the action explicitly.  Only interventions
    carrying an explicit, conservative service mapping are executable.
    """
    room_key = str(call.data.get("room_key") or "").strip()
    intervention_key = str(call.data.get("intervention_key") or "").strip() or None
    if not room_key:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="room_key_required")

    coordinators = iter_runtime_coordinators(hass)
    if not coordinators:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="integration_not_loaded")
    coordinator = coordinators[0]
    room = (coordinator.data or {}).get("rooms", {}).get(room_key)
    if not isinstance(room, dict):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_room", translation_placeholders={"room_key": room_key})

    intervention = executable_intervention(list(room.get("interventions") or []), intervention_key)
    if intervention is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_executable_intervention")

    entity_id = str(intervention.get("entity_id") or "")
    service_full = str(intervention.get("service") or "")
    if not entity_id or "." not in entity_id or "." not in service_full:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_intervention_action")
    if hass.states.get(entity_id) is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="intervention_entity_unavailable", translation_placeholders={"entity_id": entity_id})

    service_domain, service_name = service_full.split(".", 1)
    service_data = dict(intervention.get("service_data") or {})
    service_data["entity_id"] = entity_id
    try:
        await hass.services.async_call(service_domain, service_name, service_data, blocking=True)
    except HomeAssistantError:
        raise
    except Exception as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="intervention_execution_failed",
            translation_placeholders={"service": service_full},
        ) from err

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the bundled FreshAirIQ frontend once."""
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_FRONTEND_URL, str(_FRONTEND_DIR), False)]
        )
    except RuntimeError:
        pass

    # Hotfix 0.25.0.12: exactly one active frontend loading path. Storage-mode
    # Lovelace uses its managed module resource; YAML/legacy mode or a failed
    # storage registration falls back to the global extra-module URL. Loading
    # both paths at once can race in WebKit and surface as "Konfigurationsfehler".
    resource_registered = await _async_register_lovelace_resource(hass)
    if not resource_registered:
        add_extra_js_url(hass, _FRONTEND_MODULE)
    if not hass.data.get(f"{DOMAIN}_diagnostics_view_registered"):
        hass.http.register_view(FreshAirIQDiagnosticsView())
        hass.data[f"{DOMAIN}_diagnostics_view_registered"] = True
    if not hass.data.get(f"{DOMAIN}_settings_view_registered"):
        hass.http.register_view(FreshAirIQSettingsView())
        hass.http.register_view(FreshAirIQFeedbackView())
        hass.data[f"{DOMAIN}_settings_view_registered"] = True
    if not hass.services.has_service(DOMAIN, "execute_intervention"):
        hass.services.async_register(
            DOMAIN,
            "execute_intervention",
            partial(_async_execute_intervention_service, hass),
        )
    return True



def _async_sync_room_subentries(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> None:
    """Ensure every configured room has a native Home Assistant subentry.

    v0.7 installations have rooms only in parent entry data. v0.8 exposes rooms
    as config subentries so users can edit room-specific settings directly from
    the integration UI. The parent room list remains canonical for runtime
    compatibility; this function mirrors it into subentries idempotently.
    """
    rooms = [room for room in entry.data.get(CONF_ROOMS, []) if room.get("key")]
    existing = {
        sub.unique_id: sub
        for sub in entry.subentries.values()
        if sub.subentry_type == "room"
    }
    wanted = {f"room:{room['key']}" for room in rooms}

    for unique_id, subentry in list(existing.items()):
        if unique_id not in wanted:
            hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)

    for room in rooms:
        unique_id = f"room:{room['key']}"
        current = existing.get(unique_id)
        if current is None:
            hass.config_entries.async_add_subentry(
                entry,
                config_entries.ConfigSubentry(
                    data=MappingProxyType(dict(room)),
                    subentry_type="room",
                    title=room.get(CONF_ROOM_NAME, room["key"]),
                    unique_id=unique_id,
                ),
            )
        elif dict(current.data) != dict(room) or current.title != room.get(CONF_ROOM_NAME, room["key"]):
            hass.config_entries.async_update_subentry(
                entry,
                current,
                data=dict(room),
                title=room.get(CONF_ROOM_NAME, room["key"]),
            )

def _async_cleanup_removed_room_registry_entries(
    hass: HomeAssistant, entry: FreshAirIQConfigEntry
) -> None:
    """Remove FreshAirIQ room registry objects no longer in configuration.

    Home Assistant 2026.8+ devices belong to one config entry.  Once a room
    disappears from the integration, an old device can become orphaned and no
    longer be returned by config-entry scoped registry helpers.  Therefore we
    reconcile *all* registered devices by FreshAirIQ's stable identifier:
        (freshairiq, "<entry_id>:room:<room_key>")
    """
    configured_room_keys = {
        str(room.get("key"))
        for room in entry.data.get("rooms", [])
        if room.get("key")
    }

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    room_identifier_prefix = f"{entry.entry_id}:room:"

    stale_devices = []

    # DeviceRegistry.devices is mapping-like in supported Home Assistant
    # releases. Iterating the mapping itself yields device-id strings, not
    # DeviceEntry objects. Iterate its values instead. Keep a defensive
    # fallback for registry implementations exposing an iterable collection.
    registered_devices = device_registry.devices
    devices = (
        registered_devices.values()
        if hasattr(registered_devices, "values")
        else registered_devices
    )
    for device in devices:
        # A malformed/foreign registry item must never prevent FreshAirIQ from
        # starting. Valid DeviceEntry objects expose both id and identifiers.
        if not hasattr(device, "identifiers") or not hasattr(device, "id"):
            _LOGGER.debug(
                "Skipping unexpected device-registry item during room cleanup: %r",
                device,
            )
            continue

        room_key = None

        for identifier in device.identifiers:
            # Home Assistant registry identifier records may contain additional
            # metadata in newer versions. FreshAirIQ only needs the domain and
            # stable identifier value. Never assume an exact tuple length.
            try:
                identifier_domain = identifier[0]
                identifier_value = identifier[1]
            except (TypeError, IndexError):
                continue

            if (
                identifier_domain == DOMAIN
                and isinstance(identifier_value, str)
                and identifier_value.startswith(room_identifier_prefix)
            ):
                room_key = identifier_value[len(room_identifier_prefix):]
                break

        if room_key is not None and room_key not in configured_room_keys:
            stale_devices.append(device)

    for device in stale_devices:
        # Use the supported entity-registry helper so disabled entities are
        # removed as well.  Otherwise a single disabled entity could keep the
        # deleted room device alive in the UI.
        for entity_entry in list(
            er.async_entries_for_device(
                entity_registry,
                device.id,
                include_disabled_entities=True,
            )
        ):
            entity_registry.async_remove(entity_entry.entity_id)

        # Remove the now orphaned room device itself.
        device_registry.async_remove_device(device.id)


async def async_setup_entry(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> bool:
    # Older releases allowed individually valid but mutually contradictory
    # model thresholds. Repair only those relationships once at load so the
    # runtime can never start with an impossible configuration. New writes are
    # rejected by both the native options flow and the dashboard settings API.
    merged_options = {**DEFAULT_OPTIONS, **dict(entry.options)}
    repaired_options = repair_option_relationships(merged_options)
    if repaired_options != merged_options:
        updated_options = dict(entry.options)
        for key in RELATION_OPTION_KEYS:
            if repaired_options.get(key) != merged_options.get(key):
                updated_options[key] = repaired_options[key]
        hass.config_entries.async_update_entry(entry, options=updated_options)

    # Mirror legacy/parent room configuration into native room subentries.
    _async_sync_room_subentries(hass, entry)

    # Remove stale room devices/entities left in Home Assistant's registries
    # after a room was deleted from FreshAirIQ configuration.
    _async_cleanup_removed_room_registry_entries(hass, entry)

    store = LearningStore(hass, entry.entry_id, entry.data.get(CONF_LEGACY_ENTRY_ID))
    await store.async_load()
    coordinator = FreshAirIQCoordinator(hass, entry, store)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_listeners()
    set_runtime_coordinator(hass, entry, coordinator)
    try:
        async_sync_missing_entity_issue(hass, entry)
    except Exception:  # noqa: BLE001 - repair UI must never block integration setup
        _LOGGER.debug("Could not synchronize FreshAirIQ repair issues during setup", exc_info=True)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # Never leave listeners/tasks behind after a partial platform setup.
        await coordinator.async_stop_listeners()
        clear_runtime_coordinator(hass, entry)
        try:
            async_clear_missing_entity_issue(hass, entry)
        except Exception:  # noqa: BLE001 - preserve original platform setup error
            _LOGGER.debug("Could not clear FreshAirIQ repair issue after setup failure", exc_info=True)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> bool:
    """Unload FreshAirIQ transactionally.

    Keep the live coordinator and its listeners intact if Home Assistant cannot
    unload one of the entity platforms.  Stopping listeners before platform
    unload could otherwise leave an integration that HA still considers loaded
    in a non-functional half-unloaded state.
    """
    coordinator = get_runtime_coordinator(hass, entry)
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    await coordinator.async_stop_listeners()
    clear_runtime_coordinator(hass, entry)
    try:
        async_clear_missing_entity_issue(hass, entry)
    except Exception:  # noqa: BLE001 - repair cleanup is secondary to successful unload
        _LOGGER.debug("Could not clear FreshAirIQ repair issue during unload", exc_info=True)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: FreshAirIQConfigEntry) -> bool:
    """Migrate older configuration entries to the FreshAirIQ v0.8.0 schema."""
    if entry.version >= 8:
        return True

    data = dict(entry.data)
    rooms = []
    raw_rooms = data.get("rooms", [])
    if not isinstance(raw_rooms, list):
        raw_rooms = []
    for old_room in raw_rooms:
        if not isinstance(old_room, dict):
            continue
        room = dict(old_room)
        if CONF_ROOM_CONTACTS not in room:
            legacy = room.get(CONF_ROOM_CONTACT)
            room[CONF_ROOM_CONTACTS] = [legacy] if legacy else []
        room.setdefault(CONF_CONTACT_MODE, CONTACT_MODE_ANY)
        room.pop(CONF_ROOM_CONTACT, None)
        if CONF_VOLUME_MODE not in room:
            has_dimensions = all(
                room.get(key) not in (None, "")
                for key in (CONF_ROOM_LENGTH, CONF_ROOM_WIDTH, CONF_ROOM_HEIGHT)
            )
            room[CONF_VOLUME_MODE] = (
                VOLUME_MODE_DIMENSIONS if has_dimensions else VOLUME_MODE_DIRECT
            )
        room.setdefault(CONF_ROOM_FLOOR, FLOOR_GROUND)
        room.setdefault(CONF_ROOM_SORT_ORDER, len(rooms))
        room.setdefault(CONF_ROOM_INCLUDE_CALCULATIONS, True)
        room.setdefault(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN)
        contacts = room.get(CONF_ROOM_CONTACTS) or []
        if isinstance(contacts, str):
            contacts = [contacts]
        try:
            legacy_contact_delay = int(float(room.get(CONF_CONTACT_DELAY, 0)))
        except (TypeError, ValueError, OverflowError):
            legacy_contact_delay = 0
        legacy_contact_delay = max(0, min(300, legacy_contact_delay))
        room.setdefault(
            CONF_CONTACT_DELAYS,
            {contact: legacy_contact_delay for contact in contacts},
        )
        room.setdefault(
            CONF_CONTACT_ORIENTATIONS,
            {contact: room.get(CONF_ROOM_WINDOW_ORIENTATION, ORIENTATION_UNKNOWN) for contact in contacts},
        )
        rooms.append(room)
    data["rooms"] = rooms
    options = dict(entry.options)
    # v0.6.0 shipped a 10%-of-water default. Upgrade untouched/default users
    # to the dwelling-size adaptive mode; explicit custom modes remain intact.
    try:
        legacy_threshold_percent = float(options.get("min_potential_percent_total_water", 10.0))
    except (TypeError, ValueError, OverflowError):
        legacy_threshold_percent = 10.0
    if options.get("threshold_mode", "percent_total_water") == "percent_total_water" and legacy_threshold_percent == 10.0:
        options["threshold_mode"] = "adaptive_home_size"

    # Build a user-defined level list from the existing room labels. No level is
    # hard-coded in v0.8; existing labels are preserved verbatim.
    data[CONF_LEVELS] = list(dict.fromkeys(str(r.get(CONF_ROOM_FLOOR, "Unzugeordnet")) for r in rooms))

    # Do not pass subentries to async_update_entry(). Home Assistant's public
    # ConfigEntries.async_update_entry API does not accept a `subentries`
    # keyword. Existing rooms are mirrored into native subentries later during
    # async_setup_entry() through async_add_subentry()/async_update_subentry().
    # Keeping the migration limited to parent-entry data/options also makes it
    # safe and idempotent for upgrades from v0.7.x.
    hass.config_entries.async_update_entry(
        entry, data=data, options=options, version=8
    )
    return True
