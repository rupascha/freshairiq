"""Replay deterministic FreshAirIQ golden scenarios outside Home Assistant."""
from __future__ import annotations
import argparse, json, math, sys, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CUSTOM=ROOT/'custom_components'; PKG=CUSTOM/'freshairiq'

def _bootstrap():
    if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
    if 'custom_components' not in sys.modules:
        m=types.ModuleType('custom_components'); m.__path__=[str(CUSTOM)]; sys.modules['custom_components']=m
    if 'custom_components.freshairiq' not in sys.modules:
        m=types.ModuleType('custom_components.freshairiq'); m.__path__=[str(PKG)]; sys.modules['custom_components.freshairiq']=m

def _match(actual, expected):
    if isinstance(expected,dict) and 'value' in expected:
        target=expected['value']; tol=float(expected.get('abs_tol',0))
        try: return math.isclose(float(actual),float(target),abs_tol=tol,rel_tol=0)
        except (TypeError,ValueError): return False
    if isinstance(expected,dict) and 'one_of' in expected: return actual in expected['one_of']
    return actual==expected

def replay(path:Path, scenario_id:str|None=None):
    _bootstrap(); from custom_components.freshairiq.recommendation import build_recommendation
    data=json.loads(path.read_text(encoding='utf-8')); failures=[]; count=0
    for sc in data.get('scenarios',[]):
        if scenario_id and sc.get('id')!=scenario_id: continue
        count+=1; inp=dict(sc['input']); rooms=inp.pop('rooms'); options=inp.pop('options')
        out=build_recommendation(rooms,options,**inp)
        for key,expected in sc.get('expect',{}).items():
            if not _match(out.get(key),expected): failures.append(f"{sc['id']}: {key}: expected {expected!r}, got {out.get(key)!r}")
    return count,failures

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--file',default='quality/golden_scenarios/core_recommendations.json'); ap.add_argument('--scenario'); a=ap.parse_args()
    count,failures=replay(ROOT/a.file,a.scenario)
    if failures:
        print(f'Golden Scenario Replay: FAIL ({len(failures)} mismatches / {count} scenarios)'); [print(' - '+x) for x in failures]; return 1
    print(f'Golden Scenario Replay: PASS ({count} scenarios)'); return 0
if __name__=='__main__': raise SystemExit(main())
