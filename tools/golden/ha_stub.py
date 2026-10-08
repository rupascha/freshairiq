"""Minimal, deterministic stand-in for the Home Assistant APIs the coordinator uses.

Only for characterisation ("golden master") runs in a separate process. It is not a
Home Assistant emulator: it provides just enough surface for FreshAirIQ's update
cycle to run, with a frozen clock, in-memory storage and no network, so that two
versions of the coordinator can be compared byte-for-byte on identical input.
"""
from __future__ import annotations

import asyncio
import enum
import sys
import types
from datetime import datetime as _real_datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")


class Clock:
    """Single source of 'now' for dt_util, datetime.now() and perf_counter."""

    def __init__(self, start: _real_datetime) -> None:
        self.now = start
        self._perf = 1000.0

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)

    def perf_counter(self) -> float:
        self._perf += 0.001
        return self._perf


CLOCK = Clock(_real_datetime(2026, 10, 7, 21, 0, tzinfo=TZ))


class _FrozenMeta(type):
    def __instancecheck__(cls, obj: Any) -> bool:  # keep isinstance(x, datetime) working
        return isinstance(obj, _real_datetime)

    def __subclasscheck__(cls, sub: type) -> bool:
        return issubclass(sub, _real_datetime)


class FrozenDateTime(_real_datetime, metaclass=_FrozenMeta):
    @classmethod
    def now(cls, tz=None):  # noqa: D401 - mirrors datetime.now
        value = CLOCK.now
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    @classmethod
    def utcnow(cls):
        return CLOCK.now.astimezone(timezone.utc).replace(tzinfo=None)


def _module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = mod
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(_module(parent), child, mod)
    return mod


class _Generic:
    def __class_getitem__(cls, _item):
        return cls


class State:
    def __init__(self, entity_id: str, state: Any, attributes: dict | None = None, when: _real_datetime | None = None) -> None:
        self.entity_id = entity_id
        self.domain, _, self.object_id = entity_id.partition(".")
        self.state = str(state)
        self.attributes = dict(attributes or {})
        stamp = when or CLOCK.now
        self.last_changed = stamp
        self.last_updated = stamp
        self.last_reported = stamp
        self.name = self.attributes.get("friendly_name", self.object_id)


class States:
    def __init__(self) -> None:
        self._states: dict[str, State] = {}

    def get(self, entity_id: Any) -> State | None:
        return self._states.get(str(entity_id)) if entity_id else None

    def async_set(self, entity_id: str, state: Any, attributes: dict | None = None) -> None:
        old = self._states.get(entity_id)
        new = State(entity_id, state, attributes)
        if old is not None and old.state == new.state:
            new.last_changed = old.last_changed
        self._states[entity_id] = new

    def async_all(self, domain: str | None = None) -> list[State]:
        return [s for s in self._states.values() if domain is None or s.domain == domain]

    def async_entity_ids(self, domain: str | None = None) -> list[str]:
        return [s.entity_id for s in self.async_all(domain)]

    def __iter__(self):
        return iter(self._states.values())


class Services:
    def __init__(self, hass: "HomeAssistant") -> None:
        self._hass = hass
        self.forecast: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str, dict]] = []

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) == ("weather", "get_forecasts")

    async def async_call(self, domain: str, service: str, data: dict | None = None, blocking: bool = False,
                         return_response: bool = False, **_kw):
        self.calls.append((domain, service, dict(data or {})))
        if (domain, service) == ("weather", "get_forecasts"):
            ids = (data or {}).get("entity_id")
            ids = ids if isinstance(ids, list) else [ids]
            return {str(i): {"forecast": [dict(x) for x in self.forecast]} for i in ids}
        return None


class Config:
    time_zone = "Europe/Berlin"
    latitude = 0.0
    longitude = 0.0
    location_name = "Golden Home"
    language = "de"
    units = types.SimpleNamespace(temperature_unit="°C")
    config_dir = "/tmp/freshairiq-golden"

    def path(self, *parts: str) -> str:
        return "/".join((self.config_dir, *parts))


class HomeAssistant:
    def __init__(self) -> None:
        self.states = States()
        self.services = Services(self)
        self.config = Config()
        self.data: dict[str, Any] = {}
        self.bus = types.SimpleNamespace(async_fire=lambda *a, **k: None, async_listen=lambda *a, **k: (lambda: None))
        self.config_entries = types.SimpleNamespace(async_update_entry=lambda *a, **k: True, async_entries=lambda *a, **k: [])
        self._pending: list[asyncio.Future] = []
        self.loop = None

    def async_create_task(self, coro, *_a, **_k):
        task = asyncio.ensure_future(coro)
        self._pending.append(task)
        return task

    async def async_add_executor_job(self, func, *args):
        return func(*args)

    async def async_block_till_done(self) -> None:
        while self._pending:
            pending, self._pending = self._pending, []
            await asyncio.gather(*pending)


def callback(func):
    return func


class UpdateFailed(Exception):
    pass


class DataUpdateCoordinator(_Generic):
    def __init__(self, hass, logger=None, name=None, update_interval=None, config_entry=None, **_kw) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry
        self.data: Any = None
        self.last_update_success = True

    async def async_request_refresh(self) -> None:
        return None

    async def async_refresh(self) -> None:
        self.data = await self._async_update_data()

    def async_set_updated_data(self, data) -> None:
        self.data = data

    def async_update_listeners(self) -> None:
        return None


class Store:
    _MEMORY: dict[str, Any] = {}

    def __init__(self, hass, version, key, *a, **k) -> None:
        self.key = key
        self.version = version

    async def async_load(self):
        import copy
        return copy.deepcopy(self._MEMORY.get(self.key))

    async def async_save(self, data) -> None:
        import copy
        self._MEMORY[self.key] = copy.deepcopy(data)

    def async_delay_save(self, data_func, delay: float = 0) -> None:
        import copy
        self._MEMORY[self.key] = copy.deepcopy(data_func())

    async def async_remove(self) -> None:
        self._MEMORY.pop(self.key, None)


class IssueSeverity(enum.StrEnum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class _EntityRegistry:
    entities: dict = {}

    def async_get(self, entity_id):
        return None

    def async_get_entity_id(self, *a, **k):
        return None


class FakeClientSession:
    """Records every outbound request and fails it as if the network were down."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def _fail(self, method: str, url: str, *a, **k):
        self.calls.append((method, str(url)))
        raise sys.modules["aiohttp"].ClientError("golden harness: network disabled")

    def post(self, url, *a, **k):
        return self._fail("POST", url)

    def get(self, url, *a, **k):
        return self._fail("GET", url)


SESSION = FakeClientSession()


def install() -> None:
    """Register the stand-in modules (idempotent)."""
    _module("homeassistant")
    core = _module("homeassistant.core")
    core.HomeAssistant = HomeAssistant
    core.callback = callback
    core.State = State
    _module("homeassistant.const").__version__ = "2026.9.1"
    ce = _module("homeassistant.config_entries")
    ce.ConfigEntry = type("ConfigEntry", (_Generic,), {})
    _module("homeassistant.components")
    http = _module("homeassistant.components.http")
    http.HomeAssistantView = type("HomeAssistantView", (), {})
    helpers = _module("homeassistant.helpers")
    er = _module("homeassistant.helpers.entity_registry")
    er.async_get = lambda hass: _EntityRegistry()
    ir = _module("homeassistant.helpers.issue_registry")
    ir.IssueSeverity = IssueSeverity
    ir.async_create_issue = lambda *a, **k: None
    ir.async_delete_issue = lambda *a, **k: None
    ir.async_get = lambda hass: types.SimpleNamespace(issues={}, async_get_issue=lambda *a, **k: None)
    helpers.entity_registry = er
    helpers.issue_registry = ir
    _module("homeassistant.helpers.aiohttp_client").async_get_clientsession = lambda hass: SESSION
    ev = _module("homeassistant.helpers.event")
    ev.async_call_later = lambda hass, delay, action: (lambda: None)
    ev.async_track_state_change_event = lambda hass, ids, action: (lambda: None)
    ev.async_track_time_interval = lambda hass, action, interval: (lambda: None)
    _module("homeassistant.helpers.storage").Store = Store

    async def _system_info(hass):
        return {"installation_type": "golden", "version": "2026.9.1"}

    _module("homeassistant.helpers.system_info").async_get_system_info = _system_info
    uc = _module("homeassistant.helpers.update_coordinator")
    uc.DataUpdateCoordinator = DataUpdateCoordinator
    uc.UpdateFailed = UpdateFailed
    util = _module("homeassistant.util")
    dt = _module("homeassistant.util.dt")
    dt.DEFAULT_TIME_ZONE = TZ
    dt.now = lambda time_zone=None: CLOCK.now.astimezone(time_zone or TZ)
    dt.utcnow = lambda: CLOCK.now.astimezone(timezone.utc)
    dt.as_local = lambda value: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).astimezone(TZ)
    dt.as_utc = lambda value: (value.replace(tzinfo=TZ) if value.tzinfo is None else value).astimezone(timezone.utc)

    def _parse(value):
        try:
            return _real_datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    dt.parse_datetime = _parse
    util.dt = dt
    # aiohttp: only names imported at module level by telemetry/settings/log APIs.
    aio = _module("aiohttp")
    aio.ClientError = type("ClientError", (Exception,), {})
    aio.ClientTimeout = lambda **k: types.SimpleNamespace(**k)
    web = _module("aiohttp.web")
    web.Request = type("Request", (), {})
    web.Response = type("Response", (), {})
    web.json_response = lambda *a, **k: None
    aio.web = web
