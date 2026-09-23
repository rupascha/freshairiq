from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; COMP=ROOT/'custom_components'/'freshairiq'
def test_actual_room_subentry_is_fully_translated_and_documented():
 d=json.loads((COMP/'translations/de.json').read_text(encoding='utf-8')); step=d['config_subentries']['room']['step']['room_basics']
 for section in ('identity','properties','sensors','geometry','optional_sensors','optional_actuators'):
  sec=step['sections'][section]; assert sec.get('name') and sec.get('description'); assert sec.get('data'); assert set(sec['data'])==set(sec['data_description'])
 for key in ('floor','include_in_calculations','moisture_sources','ventilation_threshold_mode','reference_temperature','reference_humidity','co2','voc','pm25','illuminance','climate','exhaust_fan','supply_fan','ventilation_device','dehumidifier','humidifier','air_purifier'):
  assert key in step['data'] and key in step['data_description']; assert 'Standard:' in step['data_description'][key] and 'Beispiel:' in step['data_description'][key]
 blob=json.dumps(step,ensure_ascii=False); assert 'spätere FreshAirIQ-Funktionen' in blob; assert 'verändert die aktuelle Lüftungs-/ml-Empfehlung nicht' in blob
def test_english_fallback_matches_strings():
 strings=json.loads((COMP/'strings.json').read_text(encoding='utf-8')); en=json.loads((COMP/'translations/en.json').read_text(encoding='utf-8'))
 for section in ('config','options','config_subentries'): assert strings[section]==en[section]
def test_web_detail_has_real_scrollport_and_wheel_containment():
 card=(COMP/'frontend/freshairiq-card.js').read_text(encoding='utf-8'); assert 'height:calc(100dvh - env(safe-area-inset-top,0px) - 76px)' in card; assert 'newSubdialog.addEventListener("wheel"' in card; assert 'e.preventDefault();' in card; assert 'e.stopPropagation();' in card; assert '{ passive: false }' in card
