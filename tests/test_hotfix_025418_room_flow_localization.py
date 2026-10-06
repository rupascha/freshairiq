import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_german_room_sensor_section_has_visible_labels_and_descriptions_for_all_real_flows():
 d=json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text())
 steps=[d['options']['step'][x] for x in ('add_room','edit_room','import_ha_room_details')]
 steps += [d['config_subentries']['room']['step'][x] for x in ('room_basics','create_room','import_ha_room_details')]
 expected={'co2':'CO₂-Sensor (optional)','exhaust_fan':'Ablüfter / mechanische Lüftung (optional)','climate':'Thermostat / Klimagerät (optional)','target_temperature_mode':'Komfort-Zieltemperatur','target_temperature':'Manuelle Zieltemperatur','target_temperature_fallback':'Fallback-Zieltemperatur'}
 for st in steps:
  sec=st['sections']['sensors']
  for k,v in expected.items():
   assert sec['data'][k]==v
   assert len(sec['data_description'][k])>30

def test_optional_sensor_section_no_longer_mentions_references():
 d=json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text())
 raw=json.dumps(d,ensure_ascii=False)
 assert 'Optionale Zusatzsensoren & Referenzen' not in raw
 assert '"name": "Optionale Zusatzsensoren"' in raw
