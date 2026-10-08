from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components/freshairiq"

def test_pdf_endpoint_uses_loaded_config_entry_for_runtime_lookup():
    source=(COMP/"ventilation_log_api.py").read_text()
    assert "entry = hass.config_entries.async_get_entry(entry_id)" in source
    assert "coordinator = get_runtime_coordinator(hass, entry)" in source
    assert "get_runtime_coordinator(hass, entry_id)" not in source

def test_options_add_room_translation_has_aggregation_labels_and_help_de_en():
    cases=[
        ("de.json","Temperatur-Auswertung","Feuchte-Auswertung",("Mittelwert (empfohlen)","Median","Minimalwert","Maximalwert")),
        ("en.json","Temperature aggregation","Humidity aggregation",("Mean (recommended)","Median","Minimum","Maximum")),
    ]
    for filename,temp_label,hum_label,words in cases:
        data=json.loads((COMP/"translations"/filename).read_text())
        for step_name in ("add_room","edit_room"):
            sensors=data["options"]["step"][step_name]["sections"]["sensors"]
            assert sensors["data"]["temperature_aggregation"] == temp_label
            assert sensors["data"]["humidity_aggregation"] == hum_label
            blob=sensors["data_description"]["temperature_aggregation"]+" "+sensors["data_description"]["humidity_aggregation"]
            for word in words:
                assert word in blob

def test_strings_match_english_native_options_contract():
    data=json.loads((COMP/"strings.json").read_text())
    sensors=data["options"]["step"]["add_room"]["sections"]["sensors"]
    assert sensors["data"]["temperature_aggregation"] == "Temperature aggregation"
    assert sensors["data"]["humidity_aggregation"] == "Humidity aggregation"
    assert "Mean (recommended)" in sensors["data_description"]["temperature_aggregation"]
    assert "Median" in sensors["data_description"]["humidity_aggregation"]
