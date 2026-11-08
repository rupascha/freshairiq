"""House map: layout storage and websocket API (optional card, 0.26.5.4).

Commands (all scoped to one FreshAirIQ entry):

* ``freshairiq/house_map/get``       – stored layout (schema v1), its issues and the rooms to draw;
* ``freshairiq/house_map/propose``   – a deterministic proposal from the room setup (not saved);
* ``freshairiq/house_map/save``      – administrators only; validated, size-limited, refused on a
  revision conflict so two editors never overwrite each other silently;
* ``freshairiq/house_map/subscribe`` – wind, per-contact states and the air-path hypothesis,
  pushed on every coordinator update and after a save, only when changed.

The layout lives in its own store (``freshairiq.house_layout.<entry_id>``). Nothing here
changes the room configuration, the coordinator data, entity attributes, the recorder
or the diagnostics export.
"""
from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_CONTACT_DELAY, CONF_CONTACT_DELAYS, CONF_LEVELS, CONF_OUTDOOR_WEATHER, CONF_ROOMS, DOMAIN
from .dashboard_live import live_signal
from .house_airflow import air_paths, fan_entities, live_contact
from .house_autolayout import add_missing, propose
from .house_layout import errors, migrate, normalise, reconcile, validate
from .house_underlay import summary as underlay_summary, validate as validate_underlay
from .house_wind import wind_state
from .open_connections import connection_map
from .opening_state import normalize_opening_state

API = "house_map_v1"
GET, PROPOSE, SAVE, SUBSCRIBE = (f"{DOMAIN}/house_map/{name}" for name in ("get", "propose", "save", "subscribe"))
UNDERLAY_GET, UNDERLAY_SAVE, UNDERLAY_DELETE = (f"{DOMAIN}/house_map/underlay_{name}" for name in ("get", "save", "delete"))
STORE_VERSION = 1
MAX_LAYOUT_BYTES = 400_000


def _signal(entry_id: str) -> str:
    return f"{DOMAIN}_house_map_{entry_id}"


def _entry(hass: HomeAssistant, entry_id: str | None) -> Any:
    entries = [hass.config_entries.async_get_entry(entry_id)] if entry_id else hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        coordinator = getattr(entry, "runtime_data", None) if entry is not None else None
        if coordinator is not None and isinstance(getattr(coordinator, "data", None), dict):
            return entry
    return None


class HouseLayoutStore:
    """One entry's layout document (schema v1) with its revision."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.house_layout.{entry_id}")
        self.raw: Any = None
        self.loaded = False

    async def async_load(self) -> None:
        if not self.loaded:
            self.raw = await self._store.async_load()
            self.loaded = True

    def layout(self) -> tuple[dict[str, Any] | None, str | None]:
        return migrate(self.raw)

    def revision(self) -> int:
        return int(self.raw.get("revision", 0) or 0) if isinstance(self.raw, dict) else 0

    async def async_save(self, layout: dict[str, Any]) -> None:
        await self._store.async_save(layout)
        self.raw = layout


async def _store(hass: HomeAssistant, entry_id: str) -> HouseLayoutStore:
    stores = hass.data.setdefault(f"{DOMAIN}_house_layout_stores", {})
    store = stores.get(entry_id)
    if store is None:
        store = stores[entry_id] = HouseLayoutStore(hass, entry_id)
    await store.async_load()
    return store


class HouseUnderlayStore:
    """Floor plan templates (pictures) per floor, kept apart from the small layout document."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.house_underlay.{entry_id}")
        self.data: dict[str, Any] = {}
        self.loaded = False

    async def async_load(self) -> None:
        if not self.loaded:
            raw = await self._store.async_load()
            self.data = raw.get("floors", {}) if isinstance(raw, dict) and isinstance(raw.get("floors"), dict) else {}
            self.loaded = True

    async def async_save(self) -> None:
        await self._store.async_save({"floors": self.data})


async def _underlays(hass: HomeAssistant, entry_id: str) -> HouseUnderlayStore:
    stores = hass.data.setdefault(f"{DOMAIN}_house_underlay_stores", {})
    store = stores.get(entry_id)
    if store is None:
        store = stores[entry_id] = HouseUnderlayStore(hass, entry_id)
    await store.async_load()
    return store


async def async_remove_house_map(hass: HomeAssistant, entry_id: str) -> None:
    """The integration entry is deleted: its floor plan and template files go with it."""
    for kind in ("house_layout", "house_underlay"):
        hass.data.get(f"{DOMAIN}_{kind}_stores", {}).pop(entry_id, None)
        await Store(hass, STORE_VERSION, f"{DOMAIN}.{kind}.{entry_id}").async_remove()


def _room_configs(entry: Any) -> list[dict[str, Any]]:
    return [r for r in entry.data.get(CONF_ROOMS, []) if isinstance(r, dict)]


def _levels(entry: Any) -> list[str]:
    return [str(level) for level in entry.data.get(CONF_LEVELS, []) or []]


def _room_list(entry: Any) -> list[dict[str, Any]]:
    rooms = entry.runtime_data.data.get("rooms") or {}
    configs = {cfg.get("key"): cfg for cfg in _room_configs(entry)}
    # sizes and orientation help the editor suggest which drawn area is which room
    return [{"key": key, "name": room.get("name"), "floor": room.get("floor"),
             **{field: configs.get(key, {}).get(field) for field in ("volume", "height", "length", "width", "window_orientation")}}
            for key, room in rooms.items() if isinstance(room, dict)]


def _contact_classes(hass: HomeAssistant, rooms: list[dict[str, Any]]) -> dict[str, str]:
    """Home Assistant's device class (door, window, …) of every contact the rooms use – what the sensor is."""
    out: dict[str, str] = {}
    for room in rooms:
        for contact in room.get("contacts") if isinstance(room.get("contacts"), list) else []:
            state = hass.states.get(str(contact))
            if state is not None and state.attributes.get("device_class"):
                out[str(contact)] = str(state.attributes["device_class"])
    return out


def _proposal_input(entry: Any) -> list[dict[str, Any]]:
    return [cfg for cfg in _room_configs(entry) if cfg.get("key")]


@websocket_api.websocket_command({vol.Required("type"): GET, vol.Optional("entry_id"): str})
@websocket_api.async_response
async def ws_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    store = await _store(hass, entry.entry_id)
    layout, code = store.layout()
    keys = [r["key"] for r in _room_list(entry)]
    connection.send_result(msg["id"], {
        "house_map_api": API, "entry_id": entry.entry_id, "revision": store.revision(),
        "layout": layout, "error_code": code, "stored": store.raw is not None,
        "issues": validate(layout, keys) if layout is not None else [],
        "reconcile": reconcile(layout, keys) if layout is not None else {"missing": keys, "orphaned": []},
        "rooms": _room_list(entry), "levels": _levels(entry),
        "underlays": underlay_summary((await _underlays(hass, entry.entry_id)).data),
    })


@websocket_api.websocket_command({vol.Required("type"): PROPOSE, vol.Optional("entry_id"): str, vol.Optional("missing_only"): bool})
@websocket_api.async_response
async def ws_propose(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    rooms = _proposal_input(entry)
    keys = [r["key"] for r in rooms if r.get("key")]
    if msg.get("missing_only"):
        store = await _store(hass, entry.entry_id)
        layout, _code = store.layout()
        result = {"layout": add_missing(layout or normalise(None), rooms, _levels(entry)), "quality": None}
    else:
        result = propose(rooms, _levels(entry), connection_map(dict(entry.runtime_data.options), keys), _contact_classes(hass, rooms))
    result["layout"] = normalise(result["layout"])
    result["issues"] = validate(result["layout"], keys)
    connection.send_result(msg["id"], {"house_map_api": API, **result})


@websocket_api.websocket_command({
    vol.Required("type"): SAVE, vol.Optional("entry_id"): str,
    vol.Required("layout"): dict, vol.Required("base_revision"): int,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    if len(json.dumps(msg["layout"], default=str)) > MAX_LAYOUT_BYTES:
        connection.send_error(msg["id"], "too_large", "Layout too large")
        return
    store = await _store(hass, entry.entry_id)
    if msg["base_revision"] != store.revision():
        connection.send_error(msg["id"], "revision_conflict", f"Layout changed elsewhere (revision {store.revision()})")
        return
    layout = normalise(msg["layout"])
    issues = validate(layout, [r["key"] for r in _room_list(entry)])
    if errors(issues):
        connection.send_error(msg["id"], "invalid_layout", json.dumps(errors(issues)[:20]))
        return
    layout["revision"] = store.revision() + 1
    await store.async_save(layout)
    async_dispatcher_send(hass, _signal(entry.entry_id))
    connection.send_result(msg["id"], {"house_map_api": API, "revision": layout["revision"], "issues": issues})


def _open_for(state: Any, stable_since: Any, now: Any) -> float | None:
    """Seconds since the contact's current (debounced, for three-state contacts) state began."""
    since = dt_util.parse_datetime(str(stable_since)) if stable_since else None
    if since is None and state is not None:
        since = state.last_changed
    return max((now - since).total_seconds(), 0.0) if since is not None else None


def _entity_on(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and str(state.state).lower() in {"on", "open", "running", "fan_only", "ventilation"}


@websocket_api.websocket_command({vol.Required("type"): UNDERLAY_GET, vol.Optional("entry_id"): str, vol.Required("floor_id"): str})
@websocket_api.async_response
async def ws_underlay_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    store = await _underlays(hass, entry.entry_id)
    connection.send_result(msg["id"], {"house_map_api": API, "underlay": store.data.get(msg["floor_id"])})


@websocket_api.websocket_command({vol.Required("type"): UNDERLAY_SAVE, vol.Optional("entry_id"): str, vol.Required("underlay"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_underlay_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    underlay, code = validate_underlay(msg["underlay"])
    if underlay is None or not underlay["floor_id"]:
        connection.send_error(msg["id"], "invalid_underlay", code or "E_UNDERLAY_FLOOR")
        return
    store = await _underlays(hass, entry.entry_id)
    store.data[underlay["floor_id"]] = underlay
    await store.async_save()
    connection.send_result(msg["id"], {"house_map_api": API, "underlays": underlay_summary(store.data)})


@websocket_api.websocket_command({vol.Required("type"): UNDERLAY_DELETE, vol.Optional("entry_id"): str, vol.Required("floor_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_underlay_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    store = await _underlays(hass, entry.entry_id)
    store.data.pop(msg["floor_id"], None)
    await store.async_save()
    connection.send_result(msg["id"], {"house_map_api": API, "underlays": underlay_summary(store.data)})


def live_payload(hass: HomeAssistant, entry: Any, layout: dict[str, Any] | None) -> dict[str, Any]:
    """Wind, contact states and air paths for the map (presentation only)."""
    coordinator = entry.runtime_data
    weather = hass.states.get(entry.data.get(CONF_OUTDOOR_WEATHER)) if entry.data.get(CONF_OUTDOOR_WEATHER) else None
    attrs = weather.attributes if weather is not None else {}
    now = dt_util.utcnow()
    wind = wind_state(bearing=attrs.get("wind_bearing"), speed=attrs.get("wind_speed"), unit=attrs.get("wind_speed_unit"),
                      gust=attrs.get("wind_gust_speed"), source=weather.entity_id if weather is not None else None,
                      observed_at=weather.last_updated if weather is not None else None, now=now)
    stored_rooms = coordinator.store.data.get("rooms") if isinstance(coordinator.store.data.get("rooms"), dict) else {}
    configs = {cfg.get("key"): cfg for cfg in _room_configs(entry)}
    rooms_live: dict[str, Any] = {}
    for key, room in (coordinator.data.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        cfg = configs.get(key, {})
        mem = stored_rooms.get(key) if isinstance(stored_rooms.get(key), dict) else {}
        # F08: inside doors keep their own three-state profile and debounced mode (coordinator_room_contacts)
        three_state = set(room.get("three_state_contacts") or []) | set(mem.get("inside_three_state_contacts") or [])
        stable = {**(mem.get("inside_opening_modes") if isinstance(mem.get("inside_opening_modes"), dict) else {}),
                  **(mem.get("stable_opening_modes") if isinstance(mem.get("stable_opening_modes"), dict) else {})}
        delays = cfg.get(CONF_CONTACT_DELAYS) or {}
        stable_since = mem.get("stable_opening_since") if isinstance(mem.get("stable_opening_since"), dict) else {}
        contacts = {}
        inside = [str(c) for c in room.get("inside_contact_entities") or []]
        for contact in [*(room.get("contact_entities") or []), *inside]:
            state = hass.states.get(contact)
            contacts[contact] = live_contact(
                normalize_opening_state(state.state) if state is not None else "unknown", three_state=contact in three_state,
                stable_mode=stable.get(contact), room_active=bool(room.get("active")),
                delay_s=float(delays.get(contact, cfg.get(CONF_CONTACT_DELAY, 0)) or 0),
                open_seconds=_open_for(state, stable_since.get(contact) if contact in three_state else None, now),
            )
        # the room publishes its devices under configured_actuators (coordinator_room.py)
        actuators = room.get("configured_actuators") if isinstance(room.get("configured_actuators"), dict) else {}
        fans = fan_entities(actuators.get("exhaust_fan"))
        rooms_live[key] = {"contacts": contacts, "inside_contacts": inside, "orientations": room.get("contact_orientations") or {}, "session_active": bool(room.get("active")),
                           "exhaust_fan": fans, "exhaust_fans": {fan: _entity_on(hass, fan) for fan in fans},
                           "mechanical_exhaust_active": bool(actuators.get("mechanical_exhaust_active"))}
    usable = layout is not None and not errors(validate(layout))
    return {
        "house_map_api": API, "entry_id": entry.entry_id, "wind": wind, "rooms": rooms_live,
        "airflow": air_paths(layout, rooms_live, wind) if usable else None,
        "layout_usable": usable,
    }


@callback
@websocket_api.websocket_command({vol.Required("type"): SUBSCRIBE, vol.Optional("entry_id"): str})
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass, msg.get("entry_id"))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "FreshAirIQ is not loaded")
        return
    entry_id, msg_id = entry.entry_id, int(msg["id"])
    last: list[bytes | None] = [None]

    async def _push() -> None:
        current = _entry(hass, entry_id)
        if current is None:
            return
        store = await _store(hass, entry_id)
        layout, _code = store.layout()
        encoded = json_bytes({**live_payload(hass, current, layout), "revision": store.revision()})
        if encoded != last[0]:
            last[0] = encoded
            connection.send_message(b'{"id":' + str(msg_id).encode() + b',"type":"event","event":' + encoded + b"}")

    @callback
    def push() -> None:
        hass.async_create_task(_push(), eager_start=True)

    unsubs = [async_dispatcher_connect(hass, live_signal(entry_id), push), async_dispatcher_connect(hass, _signal(entry_id), push)]

    @callback
    def unsubscribe() -> None:
        for unsub in unsubs:
            unsub()

    connection.subscriptions[msg_id] = unsubscribe
    connection.send_result(msg_id)
    push()


@callback
def async_register_house_map(hass: HomeAssistant) -> None:
    for command in (ws_get, ws_propose, ws_save, ws_subscribe, ws_underlay_get, ws_underlay_save, ws_underlay_delete):
        websocket_api.async_register_command(hass, command)
