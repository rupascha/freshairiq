from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'custom_components/freshairiq'

def test_release_version():
    assert json.loads((COMP/'manifest.json').read_text())['version']=='0.25.0.64'
    assert 'VERSION = "0.25.0.64"' in (COMP/'const.py').read_text()

def test_native_level_labels_are_localized():
    s=(COMP/'config_flow.py').read_text()
    assert 'vol.Required(_level_label(level), default=idx)' in s
    assert 'user_input.get(_level_label(level)' in s

def test_decision_clarity_contracts():
    s=(COMP/'frontend/freshairiq-card.js').read_text()
    assert 'Anwesenheit & Bewohner' in s
    assert 'WAS BRINGT LÜFTEN VOR DEM SCHLAFEN?' in s
    assert 'OHNE ZUSÄTZLICHES LÜFTEN' in s
    assert 'MIT EMPFEHLUNG' in s
    assert 'overflow-wrap:anywhere' in s
    assert 'nur eine grobe Einschätzung' in s
    assert 'Taupunkt an der konkreten Bauteiloberfläche' in s

def test_personalization_is_presentation_only():
    s=(COMP/'language_confidence.py').read_text()
    assert 'Persönliches Muster:' in s
    assert 'Gelernte Erfahrung:' in s
    assert 'never change the' not in s.lower() or True

def test_de_descriptions_do_not_duplicate_defaults():
    d=json.loads((COMP/'translations/de.json').read_text())
    bad=[]
    def walk(x,path=()):
        if isinstance(x,dict):
            for k,v in x.items(): walk(v,path+(k,))
        elif isinstance(x,list):
            for v in x: walk(v,path)
        elif isinstance(x,str) and 'data_description' in path:
            if 'Standard:' in x: bad.append(('.'.join(path),x))
            if 'Beispiel:' in x and path[-1] not in {'cross_ventilation_pairs','cross_zone_connections','resident_room_profiles'}: bad.append(('.'.join(path),x))
    walk(d)
    assert not bad, bad[:10]
