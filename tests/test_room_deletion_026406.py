"""0.26.4.6: deleted rooms must really disappear (devices, entities, configuration).

The helpers live in the HA-bound ``__init__.py``. They are extracted from the
source and executed against small registry doubles, so the behaviour is tested
without a Home Assistant runtime (the HA runtime suite covers the wiring).
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import logging
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "custom_components/freshairiq/__init__.py"
HELPERS = (
    "_iter_device_entries",
    "_room_subentry_keys",
    "_async_drop_rooms_deleted_as_subentries",
    "_async_remember_room_subentries",
    "_rooms_pending_subentry_deletion",
    "_async_cleanup_removed_room_registry_entries",
)


class _DeviceRegistry:
    def __init__(self, devices, *, config_entry_lookup=True):
        # Mirrors Home Assistant: a UserDict-like collection whose ``.data`` maps
        # device id -> DeviceEntry (iterating it yields ids, not entries).
        self.devices = SimpleNamespace(data={d.id: d for d in devices})
        self._index = {d.id: d for d in devices}
        self.removed: list[str] = []
        self._lookup = config_entry_lookup

    def async_get(self, device_id):
        return self._index.get(device_id)

    def async_remove_device(self, device_id):
        self.removed.append(device_id)
        self._index.pop(device_id, None)


class _EntityRegistry:
    def __init__(self, by_device):
        self.by_device = by_device
        self.removed: list[str] = []

    def async_remove(self, entity_id):
        self.removed.append(entity_id)


def _load(device_registry, entity_registry):
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in HELPERS]
    assert {fn.name for fn in functions} == set(HELPERS)
    module = ast.Module(body=functions, type_ignores=[])
    dr = SimpleNamespace(
        async_get=lambda _hass: device_registry,
        async_entries_for_config_entry=lambda registry, entry_id: [
            d for d in registry.devices.data.values() if entry_id in d.config_entries
        ] if registry._lookup else (_ for _ in ()).throw(RuntimeError("no helper")),
    )
    er = SimpleNamespace(
        async_get=lambda _hass: entity_registry,
        async_entries_for_device=lambda registry, device_id, include_disabled_entities=False: [
            SimpleNamespace(entity_id=e) for e in registry.by_device.get(device_id, [])
        ],
    )
    namespace: dict[str, Any] = {
        "Any": Any, "Mapping": Mapping, "dr": dr, "er": er, "DOMAIN": "freshairiq",
        "CONF_ROOMS": "rooms", "CONF_ROOM_SUBENTRY_KEYS": "room_subentry_keys",
        "_LOGGER": logging.getLogger("test"), "HomeAssistant": object, "FreshAirIQConfigEntry": object,
    }
    exec(compile(module, str(INIT), "exec"), namespace)
    return namespace


def _device(device_id, identifier, entry_id="entry"):
    return SimpleNamespace(id=device_id, identifiers={("freshairiq", identifier)}, config_entries={entry_id})


def _entry(rooms, subentry_keys, marker=None):
    data = {"rooms": [{"key": key, "name": key} for key in rooms]}
    if marker is not None:
        data["room_subentry_keys"] = marker
    subentries = {
        f"sub-{key}": SimpleNamespace(subentry_type="room", unique_id=f"room:{key}", subentry_id=f"sub-{key}")
        for key in subentry_keys
    }
    return SimpleNamespace(entry_id="entry", data=data, subentries=subentries)


class _Hass:
    def __init__(self, entry):
        self.updates: list[dict] = []

        def update(target, *, data):
            target.data = data
            self.updates.append(data)

        self.config_entries = SimpleNamespace(async_update_entry=update)


def test_stale_room_device_and_its_entities_are_removed():
    devices = [
        _device("hub", "entry"),
        _device("kitchen", "entry:room:kitchen"),
        _device("deleted", "entry:room:test"),
        _device("orphan", "entry:room:te", entry_id="other-entry"),  # no longer linked to the entry
        _device("foreign", "otherentry:room:x"),
    ]
    device_registry = _DeviceRegistry(devices)
    entity_registry = _EntityRegistry({"deleted": ["sensor.test_a", "sensor.test_b"], "orphan": ["sensor.te_a"]})
    ns = _load(device_registry, entity_registry)

    ns["_async_cleanup_removed_room_registry_entries"](object(), _entry(["kitchen"], ["kitchen"]))

    assert sorted(device_registry.removed) == ["deleted", "orphan"]
    assert sorted(entity_registry.removed) == ["sensor.te_a", "sensor.test_a", "sensor.test_b"]


def test_device_iteration_handles_ids_lists_and_missing_helper():
    kitchen = _device("kitchen", "entry:room:kitchen")
    registry = _DeviceRegistry([kitchen], config_entry_lookup=False)
    ns = _load(registry, _EntityRegistry({}))
    assert ns["_iter_device_entries"](registry, "entry") == [kitchen]

    registry.devices = [kitchen, "kitchen", "unknown-id", object()]
    assert ns["_iter_device_entries"](registry, "entry") == [kitchen]


def test_room_deleted_as_subentry_is_removed_from_configuration():
    ns = _load(_DeviceRegistry([]), _EntityRegistry({}))
    # First start with this version: marker missing, nothing is inferred.
    entry = _entry(["kitchen", "test"], ["kitchen"])
    hass = _Hass(entry)
    assert ns["_async_drop_rooms_deleted_as_subentries"](hass, entry) == set()
    ns["_async_remember_room_subentries"](hass, entry)
    assert entry.data["room_subentry_keys"] == ["kitchen"]

    # User deletes the "test" subentry in Devices & services.
    entry = _entry(["kitchen", "test"], ["kitchen"], marker=["kitchen", "test"])
    hass = _Hass(entry)
    assert ns["_rooms_pending_subentry_deletion"](entry) == {"test"}
    assert ns["_async_drop_rooms_deleted_as_subentries"](hass, entry) == {"test"}
    assert [room["key"] for room in entry.data["rooms"]] == ["kitchen"]
    assert ns["_rooms_pending_subentry_deletion"](entry) == set()

    # A room that never had a mirrored subentry (legacy/new) is kept and mirrored later.
    entry = _entry(["kitchen", "new"], ["kitchen"], marker=["kitchen"])
    hass = _Hass(entry)
    assert ns["_async_drop_rooms_deleted_as_subentries"](hass, entry) == set()
    assert hass.updates == []
    # Unchanged marker does not rewrite the entry.
    ns["_async_remember_room_subentries"](hass, entry)
    assert hass.updates == []


def test_setup_drops_deleted_rooms_before_mirroring_and_watches_deletions():
    source = INIT.read_text(encoding="utf-8")
    setup = source[source.index("async def async_setup_entry"):source.index("async def async_unload_entry")]
    assert (
        setup.index("_async_drop_rooms_deleted_as_subentries(hass, entry)")
        < setup.index("_async_sync_room_subentries(hass, entry)")
        < setup.index("_async_remember_room_subentries(hass, entry)")
    )
    assert "_async_watch_room_subentry_deletion(hass, entry)" in setup
    # Update listeners must not be combined with OptionsFlowWithReload.
    assert "add_update_listener" not in source
    assert 'getattr(registered_devices, "data", registered_devices)' not in source
