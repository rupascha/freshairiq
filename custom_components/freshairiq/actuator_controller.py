"""Home Assistant side of the optional cover/exhaust-fan control (0.26.5.1).

Only active for rooms where the user switched it on (see ``actuator_control``).
Contacts and covers are watched directly so a cover reacts at once when a
window opens; sun protection and fans follow each coordinator update.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .actuator_control import (
    COVER_CLOSE,
    COVER_OPEN,
    COVER_POSITION,
    DEFAULT_FAN_FOLLOW_UP_MIN,
    DEFAULT_FAN_MAX_RUNTIME_MIN,
    FAN_CONTROL_OFF,
    CoverView,
    cover_setups,
    decide_cover,
    decide_fan,
    fan_demand,
    room_controls_covers,
)
from .const import DOMAIN
from .opening_state import normalize_opening_state

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
_COVER_SERVICES = {COVER_OPEN: "open_cover", COVER_CLOSE: "close_cover", "stop": "stop_cover", COVER_POSITION: "set_cover_position"}
_SET_POSITION_FEATURE = 4


def _fan_entities(room: dict[str, Any]) -> list[str]:
    raw = room.get("exhaust_fan")
    return [raw] if isinstance(raw, str) and raw else [str(x) for x in (raw or []) if x]


def _room_controls_fan(room: dict[str, Any]) -> bool:
    return str(room.get("exhaust_fan_control") or FAN_CONTROL_OFF) != FAN_CONTROL_OFF and bool(_fan_entities(room))


class ActuatorController:
    """Moves covers and switches exhaust fans for rooms that allow it."""

    def __init__(self, hass: HomeAssistant, coordinator: Any, entry: Any) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry = entry
        self._store: Store | None = None
        self._memory: dict[str, Any] = {"covers": {}, "fans": {}}
        self._unsubs: list[Any] = []
        self._rooms: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def _configured_rooms(self) -> list[dict[str, Any]]:
        return [
            room for room in self.entry.data.get("rooms", [])
            if isinstance(room, dict) and room.get("key") and (room_controls_covers(room) or _room_controls_fan(room))
        ]

    async def async_start(self) -> None:
        self._rooms = self._configured_rooms()
        if not self._rooms:
            return
        self._store = Store(self.hass, STORAGE_VERSION, f"{DOMAIN}.actuators.{self.entry.entry_id}")
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._memory["covers"] = dict(stored.get("covers") or {})
            self._memory["fans"] = dict(stored.get("fans") or {})
        watched: set[str] = set()
        for room in self._rooms:
            if room_controls_covers(room):
                for cover, setup in cover_setups(room).items():
                    watched.add(cover)
                    watched.update(setup.contacts)
        if watched:
            self._unsubs.append(async_track_state_change_event(self.hass, sorted(watched), self._on_state_change))
        self._unsubs.append(self.coordinator.async_add_listener(self._on_update))
        await self._async_evaluate(fans=True)

    async def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()
        if self._store is not None:
            await self._store.async_save(self._memory)

    @callback
    def _on_state_change(self, event: Event) -> None:
        self.hass.async_create_task(self._async_evaluate(fans=False), eager_start=True)

    @callback
    def _on_update(self) -> None:
        self.hass.async_create_task(self._async_evaluate(fans=True), eager_start=True)

    def _room_data(self, key: str) -> dict[str, Any]:
        rooms = (self.coordinator.data or {}).get("rooms") or {}
        room = rooms.get(key)
        return room if isinstance(room, dict) else {}

    def _contact_mode(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return normalize_opening_state(state.state) if state is not None else "unknown"

    def _cover_view(self, entity_id: str, zero_means_open: bool) -> CoverView:
        state = self.hass.states.get(entity_id)
        if state is None:
            return CoverView("unavailable")
        try:
            position = int(state.attributes["current_position"])
        except (KeyError, TypeError, ValueError):
            position = None
        try:
            features = int(state.attributes.get("supported_features") or 0)
        except (TypeError, ValueError):
            features = 0
        return CoverView(
            str(state.state), position,
            supports_position=bool(features & _SET_POSITION_FEATURE), zero_means_open=zero_means_open,
        )

    async def _async_evaluate(self, *, fans: bool) -> None:
        async with self._lock:
            await self._async_evaluate_locked(fans=fans)

    async def _async_evaluate_locked(self, *, fans: bool) -> None:
        changed = False
        for room in self._rooms:
            data = self._room_data(str(room["key"]))
            if room_controls_covers(room):
                changed |= await self._async_covers(room, data)
            if fans and _room_controls_fan(room):
                changed |= await self._async_fans(room, data)
        if changed and self._store is not None:
            self._store.async_delay_save(lambda: self._memory, 5)

    async def _async_covers(self, room: dict[str, Any], data: dict[str, Any]) -> bool:
        sun_auto = bool(room.get("auto_sun_protection"))
        sun_covers = set((data.get("shading") or {}).get("covers_to_close") or [])
        zero_means_open = str(room.get("cover_position_zero_means") or "closed") == "open"
        changed = False
        for cover, setup in cover_setups(room).items():
            mem = self._memory["covers"].setdefault(cover, {})
            before = dict(mem)
            commands = decide_cover(
                view=self._cover_view(cover, zero_means_open),
                setup=setup,
                contact_modes={contact: self._contact_mode(contact) for contact in setup.contacts},
                sun_auto=sun_auto,
                sun_wants_close=cover in sun_covers,
                mem=mem,
            )
            changed |= mem != before
            for command, position in commands:
                service_data: dict[str, Any] = {"entity_id": cover}
                if command == COVER_POSITION:
                    service_data["position"] = position
                await self._async_call("cover", _COVER_SERVICES[command], service_data)
        return changed

    async def _async_fans(self, room: dict[str, Any], data: dict[str, Any]) -> bool:
        fans = _fan_entities(room)
        states = [self.hass.states.get(fan) for fan in fans]
        known = [state.state for state in states if state is not None and state.state in {"on", "off"}]
        fan_on = ("on" in known) if known else None
        actuators = data.get("configured_actuators") if isinstance(data.get("configured_actuators"), dict) else {}
        mode = str(room.get("exhaust_fan_control") or FAN_CONTROL_OFF)
        mem = self._memory["fans"].setdefault(str(room["key"]), {})
        before = dict(mem)
        decision = decide_fan(
            mode=mode,
            fan_on=fan_on,
            demand=fan_demand(
                mode,
                source_active=bool(data.get("moisture_source_active")),
                recommendation=str(data.get("house_aligned_action") or ""),
                window_open=bool(actuators.get("window_open")),
            ),
            now=dt_util.now(),
            follow_up_min=float(room.get("exhaust_fan_follow_up_min", DEFAULT_FAN_FOLLOW_UP_MIN)),
            max_runtime_min=float(room.get("exhaust_fan_max_runtime_min", DEFAULT_FAN_MAX_RUNTIME_MIN)),
            mem=mem,
        )
        if decision is not None:
            await self._async_call("homeassistant", f"turn_{decision}", {"entity_id": fans})
        return mem != before

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception:  # noqa: BLE001 - a broken device must not stop the other rooms
            _LOGGER.warning("FreshAirIQ could not call %s.%s for %s", domain, service, data.get("entity_id"), exc_info=True)
