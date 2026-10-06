import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_laundry_drying_is_localized_in_both_languages():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    assert de["selector"]["moisture_source"]["options"]["laundry_drying"] == "Wäsche aufhängen / trocknen"
    assert en["selector"]["moisture_source"]["options"]["laundry_drying"] == "Hang / dry laundry"


def test_dashboard_entity_selection_uses_integrated_ha_search_picker():
    room_editor = CARD[CARD.index("    _settingsRoomEditor(key) {"):CARD.index("    _settingsPanel() {", CARD.index("    _settingsRoomEditor(key) {"))]
    assert 'data-faiq-entity-selector' in room_editor
    assert '<input class="settings-input settings-filter"' not in room_editor
    assert 'el.selector = {entity:' in CARD


def test_primary_room_settings_include_co2_exhaust_thermostat_and_temperature_targets():
    section = FLOW[FLOW.index("def _room_section_schema"):FLOW.index("def _contact_reference_field")]
    sensors = section[section.index('vol.Required("sensors")'):section.index('vol.Required("geometry")')]
    assert "CONF_ROOM_CO2" in sensors
    assert "CONF_ROOM_EXHAUST_FAN" in sensors
    assert "CONF_ROOM_CLIMATE" in sensors
    assert "CONF_ROOM_TARGET_TEMPERATURE_MODE" in sensors
    optional = section[section.index('vol.Optional("optional_actuators")'):]
    assert "CONF_ROOM_CLIMATE" not in optional


def test_native_goal_priorities_use_explicit_up_down_movement():
    block = FLOW[FLOW.index('def _goal_priority_schema'):FLOW.index('def _room_schema')]
    assert 'goal_to_move' in block
    assert 'move_direction' in block
    assert 'options=["up", "down"]' in block
    assert 'target = idx - 1 if direction == "up" else idx + 1' in block
