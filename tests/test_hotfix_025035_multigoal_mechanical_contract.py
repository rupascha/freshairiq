from pathlib import Path
from custom_components.freshairiq.const import MOISTURE_SOURCES, DEFAULT_GOAL_PRIORITIES
from custom_components.freshairiq.moisture_source import source_label

ROOT=Path(__file__).parents[1]

def test_laundry_drying_is_backend_contract_not_frontend_only():
    assert "laundry_drying" in MOISTURE_SOURCES
    assert source_label(["laundry_drying"]) == "Wäsche trocknen"

def test_mechanical_exhaust_is_first_class_session_and_learning_mode():
    src=(ROOT/'custom_components/freshairiq/coordinator.py').read_text()
    assert 'mechanical_exhaust_active = _entity_active' in src
    assert '"mechanical_exhaust" if mechanical_exhaust_active' in src
    assert 'session_mode in {"open", "tilted", "cross", "mechanical_exhaust"}' in src
    assert '"mechanical_exhaust": 0.02' in src

def test_co2_and_exhaust_are_in_primary_native_room_section():
    src=(ROOT/'custom_components/freshairiq/config_flow.py').read_text()
    section=src[src.index('def _room_section_schema'):src.index('def _normalise_room')]
    sensors=section[section.index('vol.Required("sensors")'):section.index('vol.Required("geometry")')]
    assert 'CONF_ROOM_CO2' in sensors and 'CONF_ROOM_EXHAUST_FAN' in sensors
    optional=section[section.index('vol.Optional("optional_sensors")'):]
    assert 'CONF_ROOM_CO2' not in optional.split('vol.Optional("optional_actuators")')[0]

def test_dashboard_has_goal_tracker_and_all_room_edit_fields():
    src=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
    for token in ('_goalTracker(r','room-goal-priority-1','room-target-temp-mode','room-target-temp-fallback','Ablüfter / mechanische Lüftung'):
        assert token in src

def test_de_en_native_translations_cover_new_contract():
    for lang in ('de','en'):
        src=(ROOT/f'custom_components/freshairiq/translations/{lang}.json').read_text()
        for token in ('goal_priorities','target_temperature_mode','target_temperature_fallback','exhaust_fan','co2'):
            assert token in src

def test_default_goal_order_is_complete():
    assert set(DEFAULT_GOAL_PRIORITIES)=={"humidity","co2","temperature"}
