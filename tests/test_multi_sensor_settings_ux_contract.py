from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def test_native_multi_select_contract():
    s=(ROOT/"custom_components/freshairiq/config_flow.py").read_text()
    assert 'device_class="temperature", multiple=True' in s
    assert 'device_class="humidity", multiple=True' in s

def test_import_preselects_all_detected_climate_sources():
    s=(ROOT/"custom_components/freshairiq/config_flow.py").read_text()
    assert "if key in (CONF_ROOM_TEMPERATURE, CONF_ROOM_HUMIDITY):" in s
    assert "defaults[key] = values" in s

def test_native_de_en_help_contract():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    d=de["options"]["step"]["add_room"]["sections"]["sensors"]["data_description"]["temperature"]
    e=en["options"]["step"]["add_room"]["sections"]["sensors"]["data_description"]["temperature"]
    assert "Ein einzelner Sensor reicht vollständig aus" in d and "verbleibenden gültigen Sensoren" in d
    assert "mindestens ein Klimasensor genügend neue Messwerte" in d
    assert "One sensor is fully sufficient" in e and "remaining valid sensors" in e
    assert "at least one climate sensor must provide enough new measurements" in e

def test_dashboard_de_en_help_contract():
    s=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    for x in ("Ein Sensor reicht vollständig aus.","One sensor is fully sufficient.","Für eine Lüftungsauswertung muss mindestens ein Klimasensor genügend neue Messwerte liefern.","For ventilation-session evaluation, at least one climate sensor must provide enough new measurements."):
        assert x in s
