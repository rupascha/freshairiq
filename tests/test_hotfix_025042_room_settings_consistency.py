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


# test_dashboard_entity_selection_uses_integrated_ha_search_picker: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).


def test_primary_room_settings_include_co2_exhaust_thermostat_and_temperature_targets():
    section = FLOW[FLOW.index("def _room_section_schema"):FLOW.index("def _contact_reference_field")]
    sensors = section[section.index('vol.Required("sensors")'):section.index('vol.Required("geometry")')]
    assert "CONF_ROOM_CO2" in sensors
    assert "CONF_ROOM_EXHAUST_FAN" in sensors
    assert "CONF_ROOM_CLIMATE" in sensors
    assert "CONF_ROOM_TARGET_TEMPERATURE_MODE" in sensors
    optional = section[section.index('vol.Optional("optional_actuators")'):]
    assert "CONF_ROOM_CLIMATE" not in optional


def test_native_goal_priorities_show_complete_ranked_order():
    block = FLOW[FLOW.index('def _goal_priority_schema'):FLOW.index('def _room_schema')]
    assert 'goal_priority_{idx}' in block
    assert 'wizard_back' in block
    assert 'goal_to_move' not in block
    assert 'move_direction' not in block
    assert 'duplicate_goal_order' in block
