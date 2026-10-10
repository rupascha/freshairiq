"""0.26.4.9: room devices belong to their room sub-entry (no doubled rooms in Devices & services)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.room_devices import (
    add_entities_by_room, assign_room_devices, room_device_identifier, room_subentry_ids,
)

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def _entry():
    subs = {
        "sub-schlaf": SimpleNamespace(subentry_id="sub-schlaf", subentry_type="room", unique_id="room:schlaf"),
        "sub-bad": SimpleNamespace(subentry_id="sub-bad", subentry_type="room", unique_id="room:bad"),
        "sub-other": SimpleNamespace(subentry_id="sub-other", subentry_type="something", unique_id="room:x"),
        "sub-empty": SimpleNamespace(subentry_id=None, subentry_type="room", unique_id="room:"),
        "sub-legacy": SimpleNamespace(subentry_id=None, subentry_type="room", unique_id="room:flur"),
    }
    return SimpleNamespace(entry_id="E", subentries=subs)


class _Registries:
    """Doubles that follow Home Assistant 2026.8+: one sub-entry per device, and a
    device move drops the entities still assigned to the device's old sub-entry."""

    def __init__(self):
        self.devices = {
            "d-schlaf": SimpleNamespace(id="d-schlaf", identifiers={("freshairiq", "E:room:schlaf")}, config_subentry_id=None),
            "d-bad": SimpleNamespace(id="d-bad", identifiers={("freshairiq", "E:room:bad")}, config_subentry_id="sub-bad"),
            "d-flur": SimpleNamespace(id="d-flur", identifiers={("freshairiq", "E:room:flur")}, config_subentry_id=None),
        }
        self.entities = {
            "sensor.schlaf_aktion": SimpleNamespace(entity_id="sensor.schlaf_aktion", device_id="d-schlaf", config_entry_id="E", config_subentry_id=None),
            "sensor.schlaf_hidden": SimpleNamespace(entity_id="sensor.schlaf_hidden", device_id="d-schlaf", config_entry_id="E", config_subentry_id=None),
            "sensor.foreign": SimpleNamespace(entity_id="sensor.foreign", device_id="d-schlaf", config_entry_id="OTHER", config_subentry_id=None),
            "sensor.bad_aktion": SimpleNamespace(entity_id="sensor.bad_aktion", device_id="d-bad", config_entry_id="E", config_subentry_id="sub-bad"),
        }
        self.removed: list[str] = []
        self.calls: list[str] = []

    # device registry
    def async_get_device(self, identifiers):
        if ("freshairiq", "E:room:flur") in identifiers:
            raise RuntimeError("registry hiccup")
        return next((d for d in self.devices.values() if d.identifiers & identifiers), None)

    def async_update_device(self, device_id, new_config_subentry_id):
        device = self.devices[device_id]
        old = device.config_subentry_id
        device.config_subentry_id = new_config_subentry_id
        self.calls.append(f"device:{device_id}")
        for entity in list(self.entities.values()):
            if entity.device_id == device_id and entity.config_entry_id == "E" and entity.config_subentry_id == old:
                self.removed.append(entity.entity_id)
                del self.entities[entity.entity_id]

    # entity registry
    def async_update_entity(self, entity_id, config_subentry_id):
        self.entities[entity_id].config_subentry_id = config_subentry_id
        self.calls.append(f"entity:{entity_id}")


def _entries_for_device(registry, device_id, include_disabled_entities=False):
    assert include_disabled_entities is True  # disabled entities must move too
    return [e for e in registry.entities.values() if e.device_id == device_id]


def test_room_subentries_are_mapped_by_room_key():
    assert room_subentry_ids(_entry()) == {"schlaf": "sub-schlaf", "bad": "sub-bad", "flur": "sub-legacy"}
    assert room_subentry_ids(SimpleNamespace()) == {}
    assert room_device_identifier("freshairiq", "E", "bad") == ("freshairiq", "E:room:bad")


def test_existing_room_device_moves_without_losing_a_single_entity():
    regs = _Registries()
    moved = assign_room_devices(regs, regs, _entries_for_device, _entry(), "freshairiq")
    assert moved == ["schlaf"]  # bad is already there, flur's registry lookup failed safely
    assert regs.removed == []
    assert regs.entities["sensor.schlaf_aktion"].config_subentry_id == "sub-schlaf"
    assert regs.entities["sensor.schlaf_hidden"].config_subentry_id == "sub-schlaf"
    assert regs.entities["sensor.foreign"].config_subentry_id is None  # other integrations untouched
    assert regs.devices["d-schlaf"].config_subentry_id == "sub-schlaf"
    # entities are moved before the device, otherwise HA would drop them
    assert regs.calls.index("device:d-schlaf") > regs.calls.index("entity:sensor.schlaf_hidden")
    assert assign_room_devices(regs, regs, _entries_for_device, _entry(), "freshairiq") == []  # idempotent


def test_wrong_order_would_have_deleted_entities():
    regs = _Registries()
    regs.async_update_device("d-schlaf", "sub-schlaf")
    assert "sensor.schlaf_aktion" in regs.removed  # the double reproduces HA's cleanup


def test_room_entities_are_added_to_their_subentry():
    calls = []

    def add(entities, **kwargs):
        calls.append((list(entities), kwargs))

    add_entities_by_room(add, _entry(), ["house"], {"schlaf": ["s1", "s2"], "bad": [], "keller": ["k1"]})
    assert calls == [
        (["house"], {}),
        (["s1", "s2"], {"config_subentry_id": "sub-schlaf"}),
        (["k1"], {}),
    ]
    calls.clear()
    add_entities_by_room(add, _entry(), [], {})
    assert calls == []


def test_platforms_and_setup_use_the_subentry_layout():
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert "assign_room_devices(dr.async_get(hass), er.async_get(hass), er.async_entries_for_device, entry, DOMAIN)" in init
    assert init.index("_async_sync_room_subentries(hass, entry)\n") < init.index("assign_room_devices(") < init.index("async_forward_entry_setups")
    for name in ("sensor.py", "binary_sensor.py"):
        assert "add_entities_by_room(async_add_entities, entry, " in (COMP / name).read_text(encoding="utf-8")
    for name in ("number.py", "select.py", "button.py"):
        assert "room" not in (COMP / name).read_text(encoding="utf-8").split("async_setup_entry", 1)[1].split("class ", 1)[0]
