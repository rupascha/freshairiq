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
    FAN_COMMAND_TIMEOUT_S,
    FAN_CONTROL_RECOMMENDATION,
    FAN_OFF_CONFIRM_S,
    CoverView,
    cover_setups,
    decide_cover,
    decide_fan,
    fan_demand,
    room_controls_covers,
    settle_removed_off,
)
from .const import DOMAIN
from .fan_automation import fan_restart_lock_min, fan_trace_row
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
        self._memory: dict[str, Any] = {"covers": {}, "fans": {}, "fan_trace": []}
        self._unsubs: list[Any] = []
        self._rooms: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def _configured_rooms(self) -> list[dict[str, Any]]:
        return [
            room for room in self.entry.data.get("rooms", [])
            if isinstance(room, dict) and room.get("key") and (room_controls_covers(room) or _room_controls_fan(room))
        ]

    async def async_start(self) -> None:
        if await self._async_attach():
            await self._async_evaluate(fans=True)

    async def _async_attach(self) -> bool:
        self._rooms = self._configured_rooms()
        # 0.26.5.3: always follow coordinator updates, also with no controlled
        # room yet, so a control switched on later works without a restart.
        self._unsubs.append(self.coordinator.async_add_listener(self._on_update))
        if not self._rooms:
            return False
        await self._async_load_store()
        watched: set[str] = set()
        for room in self._rooms:
            if room_controls_covers(room):
                for cover, setup in cover_setups(room).items():
                    watched.add(cover)
                    watched.update(setup.contacts)
        if watched:
            self._unsubs.append(async_track_state_change_event(self.hass, sorted(watched), self._on_state_change))
        return True

    async def async_sync(self) -> None:
        """Re-read the room setup when it changed since the last attach (0.26.5.3).

        Covers every editor (options flow pages, room sub-entries, dashboard),
        including a cover, window contact or follow switch added to a room
        whose control was already on.
        """
        if self._configured_rooms() != self._rooms:
            await self.async_reload()

    async def async_reload(self) -> None:
        """Pick up an edited room setup without restarting Home Assistant (0.26.5.2).

        Before, switching the control on for an existing room only took effect
        after a restart. A fan FreshAirIQ switched on in a room whose fan
        control was switched off again is switched off.
        """
        async with self._lock:
            while self._unsubs:
                self._unsubs.pop()()
            before = {str(room["key"]): room for room in self._rooms}
            await self._async_attach()
            still = {str(room["key"]) for room in self._rooms if _room_controls_fan(room)}
            for key, room in before.items():
                mem = self._memory["fans"].get(key)
                if key not in still and isinstance(mem, dict) and mem.get("owned"):
                    # 0.26.5.4 (review A06): the switch-off is recorded with its result; the room is
                    # no longer controlled, so a fan that did not react stays visible in the trace
                    # audit S05: a fan another controlled room still needs stays on; it is switched off
                    # once nobody needs it any more (see _async_settle_removed)
                    needed = set().union(*self._fan_demand_by_room().values())
                    now_off = [fan for fan in _fan_entities(room) if fan not in needed]
                    sent = await self._async_call("homeassistant", "turn_off", {"entity_id": now_off}) if now_off else True
                    # audit P2-08: followed until the fans report off (or the timeout); "waiting" while only
                    # fans another room still needs are left (audit N02)
                    mem.update(owned=False, command="off", command_at=dt_util.now().isoformat(),
                               command_state=("pending" if now_off else "waiting") if sent else "failed", reason="control_removed",
                               off_entities=now_off if sent else None,
                               deferred_off=[fan for fan in _fan_entities(room) if fan in needed] or None)
                    self._trace(key, FAN_CONTROL_OFF, mem, dt_util.now())
        if self._rooms or self._removed_pending():
            await self._async_evaluate(fans=True)

    async def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()
        # nothing is written for an installation without any controlled device (audit S11 loads early)
        if self._store is not None and (self._rooms or any(self._memory.values())):
            await self._store.async_save(self._memory)

    @callback
    def _on_state_change(self, event: Event) -> None:
        self.hass.async_create_task(self._async_evaluate(fans=False), eager_start=True)

    @callback
    def _on_update(self) -> None:
        self.hass.async_create_task(self._async_update(), eager_start=True)

    async def _async_load_store(self) -> None:
        if self._store is None:
            self._store = Store(self.hass, STORAGE_VERSION, f"{DOMAIN}.actuators.{self.entry.entry_id}")
            stored = await self._store.async_load()
            if isinstance(stored, dict):
                self._memory["covers"] = dict(stored.get("covers") or {})
                self._memory["fans"] = dict(stored.get("fans") or {})
                self._memory["fan_trace"] = [row for row in (stored.get("fan_trace") or []) if isinstance(row, dict)][-30:]

    async def _async_update(self) -> None:
        # audit S11: loaded also without a controlled room – a switch-off still pending before a
        # restart (control removed) is followed to its result
        await self._async_load_store()
        if self._configured_rooms() != self._rooms:
            await self.async_reload()
        elif self._rooms or self._removed_pending():
            await self._async_evaluate(fans=True)

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
        changed = await self._async_settle_removed() if fans else False
        demanded = self._fan_demand_by_room() if fans else {}
        for room in self._rooms:
            data = self._room_data(str(room["key"]))
            if room_controls_covers(room):
                changed |= await self._async_covers(room, data)
            if fans and _room_controls_fan(room):
                shared = set().union(*(d for k, d in demanded.items() if k != str(room["key"])))
                changed |= await self._async_fans(room, data, needed_elsewhere=shared)
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

    def _removed_pending(self) -> bool:
        return any(isinstance(mem, dict) and mem.get("reason") == "control_removed" and (mem.get("command_state") == "pending" or mem.get("deferred_off"))
                   for mem in self._memory["fans"].values())

    async def _async_settle_removed(self) -> bool:
        """Result of the switch-off sent when a room's fan control was removed (audit P2-08, S05)."""
        changed = False
        for key, mem in self._memory["fans"].items():
            if not (isinstance(mem, dict) and mem.get("reason") == "control_removed"):
                continue
            # audit N02: the switch-off already sent gets its result while a shared fan still waits
            sent_to = list(mem.get("off_entities") or [])
            fan_on, _all_on, _count, all_off = self._fan_states(sent_to)
            if settle_removed_off(mem, fan_on, dt_util.now(), all_off=all_off):
                self._remember_removed_result(mem, sent_to)
                self._trace(str(key), FAN_CONTROL_OFF, mem, dt_util.now())
                changed = True
            elif mem.get("off_failed") and self._fan_states(list(mem["off_failed"]))[3]:
                # a fan that did not react reports off later: the failure is resolved
                mem["off_failed"] = None
                if mem.get("command_state") == "failed" and not mem.get("deferred_off"):
                    mem["command_state"] = "confirmed"
                    self._trace(str(key), FAN_CONTROL_OFF, mem, dt_util.now())
                changed = True
            deferred = list(mem.get("deferred_off") or [])
            if not deferred or mem.get("command_state") == "pending" or set(deferred) & set().union(*self._fan_demand_by_room().values()):
                continue  # nothing waits, the first switch-off is still open, or another room still needs it
            sent = await self._async_call("homeassistant", "turn_off", {"entity_id": deferred})
            mem.update(off_entities=deferred, deferred_off=None, command_at=dt_util.now().isoformat(),
                       command_state="pending" if sent else "failed")
            self._trace(str(key), FAN_CONTROL_OFF, mem, dt_util.now())
            changed = True
        return changed

    @staticmethod
    def _remember_removed_result(mem: dict[str, Any], sent_to: list[str]) -> None:
        """Audit F02: a failed part stays failed – "confirmed" only when every fan FreshAirIQ switched off is off."""
        if mem.get("command_state") == "failed":
            mem["off_failed"] = sorted({*(mem.get("off_failed") or []), *sent_to})
        elif mem.get("off_failed"):
            mem["command_state"] = "failed"

    def _fan_states(self, fans: list[str]) -> tuple[bool | None, bool, int, bool]:
        """(any on – None without a known state, all on, number on, all off).

        audit S02: "all off" only when every fan reports off – "off + unavailable" is not.
        """
        known = [state.state for state in (self.hass.states.get(fan) for fan in fans) if state is not None and state.state in {"on", "off"}]
        count = known.count("on")
        complete = len(known) == len(fans)
        return (count > 0) if known else None, complete and count == len(fans), count, complete and count == 0

    def fan_snapshot(self, key: str) -> dict[str, Any]:
        """What FreshAirIQ is doing with the room's fan (0.26.5.4; no entity IDs)."""
        mem = self._memory["fans"].get(str(key))
        mem = mem if isinstance(mem, dict) else {}
        return {
            "owned": bool(mem.get("owned")),
            "blocked": bool(mem.get("blocked")),
            "command": mem.get("command"),
            "command_state": mem.get("command_state"),
            "command_at": mem.get("command_at"),
            "reason": mem.get("reason"),
            "off_pending_since": mem.get("off_pending_since"),
            "completed_at": mem.get("completed_at"),
            "restart_locked": self._restart_locked(key, mem),
            "own_off": (mem.get("own_off") or {}).get("state"),
            **self._fan_group(key),
        }

    def _fan_group(self, key: str) -> dict[str, Any]:
        """Audit P1-05: how many of several fans are on (no entity IDs); empty for a single fan."""
        room = next((r for r in self._rooms if str(r.get("key")) == str(key)), {})
        fans = _fan_entities(room) if room else []
        if len(fans) < 2:
            return {}
        return {"fans_total": len(fans), "fans_on": self._fan_states(fans)[2]}

    def _restart_locked(self, key: str, mem: dict[str, Any]) -> bool:
        room = next((r for r in self._rooms if str(r.get("key")) == str(key)), {})
        if str(room.get("exhaust_fan_control") or FAN_CONTROL_OFF) != FAN_CONTROL_RECOMMENDATION:
            return False
        try:
            completed = dt_util.parse_datetime(str(mem.get("completed_at") or ""))
        except (TypeError, ValueError):
            completed = None
        lock = fan_restart_lock_min(getattr(self.coordinator, "options", None) or {})
        return completed is not None and (dt_util.now() - completed).total_seconds() < lock * 60.0

    def fan_trace(self) -> list[dict[str, Any]]:
        """Recent fan commands for the support diagnostics (room key, command, reason, result)."""
        return [dict(row) for row in self._memory.get("fan_trace") or []]

    def _demand(self, room: dict[str, Any], data: dict[str, Any]) -> bool:
        actuators = data.get("configured_actuators") if isinstance(data.get("configured_actuators"), dict) else {}
        return fan_demand(
            str(room.get("exhaust_fan_control") or FAN_CONTROL_OFF),
            source_active=bool(data.get("moisture_source_active")),
            recommendation=str(data.get("house_aligned_action") or ""),
            window_open=bool(actuators.get("window_open")),
        )

    def _fan_demand_by_room(self) -> dict[str, set[str]]:
        """Fans each controlled room needs right now (0.26.5.3: one fan, several rooms)."""
        return {
            str(room["key"]): set(_fan_entities(room))
            for room in self._rooms
            if _room_controls_fan(room) and self._demand(room, self._room_data(str(room["key"])))
        }

    async def _async_fans(self, room: dict[str, Any], data: dict[str, Any], *, needed_elsewhere: set[str] = frozenset()) -> bool:
        fans = _fan_entities(room)
        fan_on, all_on, _count, all_off = self._fan_states(fans)  # 0.26.5.4 (review A05): confirmed only when all on
        mode = str(room.get("exhaust_fan_control") or FAN_CONTROL_OFF)
        mem = self._memory["fans"].setdefault(str(room["key"]), {})
        before = dict(mem)
        now = dt_util.now()
        if fan_on and mem.get("owned") and set(fans) & needed_elsewhere and not self._demand(room, data):
            # another room still needs this fan: it stays on, this room keeps
            # trying to switch it off once nobody needs it any more
            if mem.get("command") == "on" and mem.get("command_state") == "pending" and all_on:
                mem["command_state"] = "confirmed"  # the start this room sent is reported
            own_changed = await self._async_stop_own_fans(room, [fan for fan in fans if fan not in needed_elsewhere], mode, mem, now)
            return mem != before or own_changed  # audit F01: own_off changes in place (a flat copy cannot see it)
        mem.pop("own_off", None)  # the room decides for its whole group again
        options = getattr(self.coordinator, "options", None) or {}
        recommendation = mode == FAN_CONTROL_RECOMMENDATION
        decision = decide_fan(
            mode=mode,
            fan_on=fan_on,
            demand=self._demand(room, data),
            now=now,
            follow_up_min=float(room.get("exhaust_fan_follow_up_min", DEFAULT_FAN_FOLLOW_UP_MIN)),
            max_runtime_min=float(room.get("exhaust_fan_max_runtime_min", DEFAULT_FAN_MAX_RUNTIME_MIN)),
            mem=mem,
            off_confirm_s=FAN_OFF_CONFIRM_S if recommendation else 0.0,
            restart_lock_min=fan_restart_lock_min(options) if recommendation else 0.0,
            urgent=bool(data.get("moisture_source_active")) or _co2_critical(data, options),
            safety_off=_moisture_coming_in(data),
            all_on=all_on,
            all_off=all_off,
        )
        if decision is not None:
            if not await self._async_call("homeassistant", f"turn_{decision}", {"entity_id": fans}):
                mem["command_state"] = "failed"
                if decision == "on":
                    mem["owned"] = False
                    mem["blocked"] = True
        # 0.26.5.4 (review A10): the trace also records how a command ended (confirmed / failed)
        if decision is not None or (before.get("command_state") == "pending" and mem.get("command_state") != "pending"):
            self._trace(str(room["key"]), mode, mem, now)
        return mem != before

    async def _async_stop_own_fans(self, room: dict[str, Any], own: list[str], mode: str, mem: dict[str, Any], now: Any) -> bool:
        """Audit S03: the shared fan stays on for the other room, this room's own fans are switched off.

        Same off confirmation as a normal switch-off in the recommendation mode.
        """
        own_off = mem.get("own_off") if isinstance(mem.get("own_off"), dict) else None
        if own_off:
            # audit N01: one switch-off, followed to its result (no repeated commands); a fan switched on
            # again by hand afterwards is left alone
            if own_off.get("state") == "pending":
                _on, _all_on, _count, all_off = self._fan_states(list(own_off.get("entities") or []))
                at = dt_util.parse_datetime(str(own_off.get("at") or "")) or now
                if all_off or (now - at).total_seconds() >= FAN_COMMAND_TIMEOUT_S:
                    own_off["state"] = "confirmed" if all_off else "failed"
                    self._trace(str(room["key"]), mode, {"command": "off", "reason": "shared_fan_kept", "command_state": own_off["state"]}, now)
                    return True
            return False
        running = [fan for fan in own if (state := self.hass.states.get(fan)) is not None and state.state == "on"]
        if not running:
            mem.pop("off_pending_since", None)
            return False
        pending = dt_util.parse_datetime(str(mem.setdefault("off_pending_since", now.isoformat()))) or now
        if mode == FAN_CONTROL_RECOMMENDATION and (now - pending).total_seconds() < FAN_OFF_CONFIRM_S:
            return False
        sent = await self._async_call("homeassistant", "turn_off", {"entity_id": running})
        mem.pop("off_pending_since", None)
        mem["own_off"] = {"entities": running, "at": now.isoformat(), "state": "pending" if sent else "failed"}
        self._trace(str(room["key"]), mode, {"command": "off", "reason": "shared_fan_kept", "command_state": mem["own_off"]["state"]}, now)
        return True

    def _trace(self, room_key: str, mode: str, mem: dict[str, Any], now: Any) -> None:
        self._memory["fan_trace"] = [*self._memory.get("fan_trace", []), fan_trace_row(room_key, mode, mem, now)][-30:]

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> bool:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception:  # noqa: BLE001 - a broken device must not stop the other rooms
            _LOGGER.warning("FreshAirIQ could not call %s.%s for %s", domain, service, data.get("entity_id"), exc_info=True)
            return False
        return True


def _moisture_coming_in(data: dict[str, Any]) -> bool:
    """The running fan brings in moisture: stop without waiting (protection)."""
    try:
        return bool(data.get("active")) and float(data.get("moisture_effect_next_5_min_ml")) < 0
    except (TypeError, ValueError):
        return False


def _co2_critical(data: dict[str, Any], options: dict[str, Any]) -> bool:
    try:
        return bool(data.get("co2_available", True)) and float(data.get("co2")) >= float(options.get("co2_critical", 1400.0))
    except (TypeError, ValueError):
        return False
