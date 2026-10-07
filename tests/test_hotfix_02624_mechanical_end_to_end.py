from pathlib import Path

from custom_components.freshairiq.climate_sources import entity_ids
from custom_components.freshairiq.intervention import build_interventions, executable_intervention

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text()
COORD = (ROOT / 'custom_components/freshairiq/coordinator.py').read_text()
DE = (ROOT / 'custom_components/freshairiq/translations/de.json').read_text()


def _room(**kw):
    base = {'action': 'Wait', 'humidity': 75.0, 'temperature_c': 22.0, 'co2_ppm': 700.0, 'voc': None, 'pm25': None}
    base.update(kw)
    return base


def _options():
    return {'high_rh': 68.0, 'start_rh': 62.0, 'co2_warn': 1000.0, 'voc_warn': 600.0, 'pm25_warn': 15.0}


def test_exhaust_contract_accepts_legacy_scalar_and_multiple_entities():
    assert entity_ids('fan.bad') == ['fan.bad']
    assert entity_ids(['fan.bad_low', 'switch.bad_high']) == ['fan.bad_low', 'switch.bad_high']
    assert 'multiple=True' in FLOW.split('CONF_ROOM_EXHAUST_FAN', 1)[1].split(')', 4)[0] or 'multiple=True' in FLOW


def test_multiple_stage_entities_are_detection_only_not_auto_selected():
    rows = build_interventions(room=_room(action='Okay'), config={'exhaust_fan': ['switch.bad_low', 'switch.bad_high']}, options=_options())
    row = next(item for item in rows if item['key'] == 'extract_moisture')
    assert row['entity_id'] is None
    assert row['service'] is None
    assert row['automatic_safe'] is False
    assert executable_intervention(rows, 'extract_moisture') is None
    assert 'keine Stufe automatisch' in row['reason']


def test_single_exhaust_keeps_legacy_executable_behaviour():
    rows = build_interventions(room=_room(action='Okay'), config={'exhaust_fan': 'fan.bad'}, options=_options())
    row = next(item for item in rows if item['key'] == 'extract_moisture')
    assert row['entity_id'] == 'fan.bad'
    assert row['service'] == 'fan.turn_on'
    assert row['automatic_safe'] is True


def test_coordinator_listener_expands_exhaust_lists_instead_of_adding_list_object():
    assert 'entities.update(entity_ids(room.get(CONF_ROOM_EXHAUST_FAN)))' in COORD
    assert 'entities.add(room[key])' not in COORD.split('CONF_ROOM_EXHAUST_FAN', 1)[0][-300:]


def test_room_icon_is_present_once_in_quick_schema_and_in_central_schema():
    quick = FLOW.split('def _room_schema', 1)[1].split('def _room_section_schema', 1)[0]
    central = FLOW.split('def _room_section_schema', 1)[1].split('def _contact_reference_field', 1)[0]
    assert quick.count('selector.IconSelector()') == 1
    assert central.count('selector.IconSelector()') >= 1
    assert 'selector.IconSelector()' in quick
    assert 'selector.IconSelector()' in central


def test_german_exhaust_copy_explains_multiple_stages_without_english_new_terms():
    assert 'Ablüfter / mechanische Lüftung' in DE
    assert 'einen oder mehrere Ablüfter bzw. Entitäten für Lüfterstufen' in DE
    assert 'keine Stufe automatisch' in DE
    assert 'Exhaust fan' not in DE
    assert 'fan stages' not in DE.lower()


def test_exhaust_recommendation_is_suppressed_when_canonical_decision_says_not_to_ventilate():
    for action in ("Do not ventilate", "Wait", "Close"):
        rows = build_interventions(
            room=_room(action=action, humidity=75.0, moisture_source_active=True),
            config={"exhaust_fan": "fan.bad"},
            options=_options(),
        )
        assert not any(item["key"] == "extract_moisture" for item in rows), action


def test_running_exhaust_is_not_recommended_to_be_switched_on_again():
    states = {"fan.bad": "on"}
    rows = build_interventions(
        room=_room(action="Ventilate", humidity=75.0, moisture_source_active=True),
        config={"exhaust_fan": "fan.bad"},
        options=_options(),
        entity_state=states.get,
    )
    assert not any(item["key"] == "extract_moisture" for item in rows)


def test_any_running_stage_suppresses_multi_stage_start_recommendation():
    states = {"switch.bad_low": "off", "switch.bad_high": "on"}
    rows = build_interventions(
        room=_room(action="Ventilate", humidity=75.0, moisture_source_active=True),
        config={"exhaust_fan": ["switch.bad_low", "switch.bad_high"]},
        options=_options(),
        entity_state=states.get,
    )
    assert not any(item["key"] == "extract_moisture" for item in rows)


def test_co2_alone_does_not_create_mechanical_action_against_canonical_wait():
    rows = build_interventions(
        room=_room(action="Wait", co2=1500.0),
        config={"ventilation_device": "fan.hrv"},
        options=_options(),
    )
    assert not any(item["key"] == "mechanical_ventilation" for item in rows)


def test_inactive_configured_exhaust_still_allows_non_conflicting_start_recommendation():
    rows = build_interventions(
        room=_room(action="Ventilate", humidity=75.0, moisture_source_active=True),
        config={"exhaust_fan": ["switch.bad_low", "switch.bad_high"]},
        options=_options(),
        entity_state={"switch.bad_low": "off", "switch.bad_high": "off"}.get,
    )
    row = next(item for item in rows if item["key"] == "extract_moisture")
    assert row["service"] is None
    assert row["automatic_safe"] is False
