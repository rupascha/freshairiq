import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DE=json.loads((ROOT/'custom_components/freshairiq/translations/de.json').read_text(encoding='utf-8'))
EN=json.loads((ROOT/'custom_components/freshairiq/translations/en.json').read_text(encoding='utf-8'))
STR=json.loads((ROOT/'custom_components/freshairiq/strings.json').read_text(encoding='utf-8'))

def leaves(obj,p=''):
    out={}
    for k,v in obj.items():
        q=f'{p}.{k}' if p else k
        if isinstance(v,dict): out.update(leaves(v,q))
        else: out[q]=v
    return out

def test_key_parity_and_strings_sync():
    de,en,st=leaves(DE),leaves(EN),leaves(STR)
    assert set(de)==set(en)
    assert en==st

def test_critical_english_help_preserves_semantics():
    e=leaves(EN)
    checks={
      'config.step.user.description':['without configuring any rooms','Devices & services','dashboard remains available'],
      'options.step.init.description':['default value','example','take effect immediately'],
      'options.step.contact_delays.description':['Default: 0 s','120 s','two minutes'],
      'config_subentries.room.step.room_delays.description':['Default: 0 s','120 s','two minutes','saved immediately'],
      'config_subentries.room.step.user.sections.optional_sensors.description':['VOC/TVOC','PM2.5','lux','30-day diagnostics'],
      'config.step.room.data_description.voc':['volatile organic compounds','ml forecast','30-day diagnostics'],
      'config.step.room.data_description.pm25':['2.5 µm','µg/m³','ml forecast'],
      'config.step.room.data_description.illuminance':['lux (lx)','ml forecast','30-day diagnostics'],
    }
    for key,needles in checks.items():
        for needle in needles: assert needle in e[key], (key,needle,e[key])

def test_no_extreme_information_loss_for_long_help_texts():
    de,en=leaves(DE),leaves(EN)
    bad=[]
    for key,d in de.items():
        e=en.get(key)
        if isinstance(d,str) and isinstance(e,str) and len(d)>=100 and len(e)<len(d)*0.42:
            bad.append((key,len(d),len(e)))
    assert not bad, bad
