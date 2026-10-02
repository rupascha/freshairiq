import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CARD=(ROOT/'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()

def _flat(obj,p=''):
    out={}
    for k,v in obj.items():
        q=f'{p}.{k}' if p else k
        if isinstance(v,dict): out.update(_flat(v,q))
        elif isinstance(v,str): out[q]=v
    return out

def test_dashboard_editor_uses_central_i18n_keys():
    assert '_editorDE() ? "DASHBOARD-DESIGN"' not in CARD
    for key in ('editor.dashboard_design','editor.dashboard_design_help','editor.dashboard_style','editor.dashboard_style_help','editor.classic'):
        assert f'"{key}"' in CARD
        assert f'this._t("{key}")' in CARD

def test_legacy_bridge_agrees_with_canonical_translation_for_exact_unique_texts():
    de=_flat(json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text()))
    en=_flat(json.loads((ROOT/'custom_components/freshairiq/translations/en.json').read_text()))
    reverse={}
    for k,v in de.items(): reverse.setdefault(v,[]).append(k)
    m=re.search(r'const FAIQ_NATIVE_EN = (\[.*?\]);\n',CARD,re.S); assert m
    pairs=json.loads(m.group(1))
    bad=[]
    for german,english in pairs:
        expected={en[k] for k in reverse.get(german,[]) if k in en}
        if len(expected)==1 and english not in expected: bad.append((german,english,next(iter(expected))))
    assert not bad

def test_config_flow_title_is_semantically_equivalent():
    de=json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text())
    en=json.loads((ROOT/'custom_components/freshairiq/translations/en.json').read_text())
    base=json.loads((ROOT/'custom_components/freshairiq/strings.json').read_text())
    assert de['config']['step']['user']['title']=='FreshAirIQ hinzufügen'
    assert en['config']['step']['user']['title']=='Add FreshAirIQ'
    assert base['config']['step']['user']['title']=='Add FreshAirIQ'
