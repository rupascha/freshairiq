from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _discovery_block() -> str:
    return FLOW.split("def _ha_area_entity_defaults", 1)[1].split("def _ha_area_options", 1)[0]


def test_discovery_uses_ha_entity_and_device_registries():
    block = _discovery_block()
    assert "entity_registry as er" in FLOW
    assert "device_registry as dr" in FLOW
    assert "er.async_get(self.hass)" in block
    assert "dr.async_get(self.hass)" in block


def test_child_device_and_device_area_inheritance_uses_effective_area():
    block = _discovery_block()
    assert "dr.async_get_effective_area_id(self.hass, device)" in block
    assert "entity_entry.area_id" in block


def test_only_entities_from_selected_area_are_candidates():
    block = _discovery_block()
    assert "if entity_area_id != area_id:" in block
    assert "continue" in block
    assert "entity_entry.disabled_by is not None" in block


def test_supported_room_local_sensor_classes_are_discovered():
    block = _discovery_block()
    for token in ('"temperature"', '"humidity"', '"carbon_dioxide"', '"illuminance"', '"climate"'):
        assert token in block
    for token in ('"door"', '"garage_door"', '"opening"', '"window"'):
        assert token in block


def test_explicit_area_temperature_and_humidity_have_priority():
    block = _discovery_block()
    assert 'getattr(area, "temperature_entity_id", None)' in block
    assert 'getattr(area, "humidity_entity_id", None)' in block
    assert "if key not in defaults and len(values) == 1" in block


def test_ambiguous_single_value_sensors_are_not_guessed():
    block = _discovery_block()
    assert "len(values) == 1" in block
    assert "defaults[key] = values[0]" in block


def test_contacts_can_be_prefilled_as_multiple_entities():
    block = _discovery_block()
    assert "defaults[CONF_ROOM_CONTACTS] = contacts" in block


def test_imported_defaults_are_forwarded_to_existing_room_form():
    block = FLOW.split("async def async_step_import_ha_room_details", 1)[1].split("async def async_step_add_room", 1)[0]
    assert "**imported" in block
    assert "_room_section_schema(defaults" in block
    assert "CONF_ROOM_INCLUDE_CALCULATIONS: False" in block


def test_existing_rooms_are_not_modified_by_discovery():
    block = _discovery_block()
    assert "self._rooms()" not in block
    assert "async_update_entry" not in block


def test_release_version_025129():
    # Historical regression: prove the 0.25.1.29 release evidence remains preserved.
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.29.md").is_file()
