"""Atomically bump FreshAirIQ release metadata and current-version contracts."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'custom_components/freshairiq/manifest.json'

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('version'); args=ap.parse_args()
    new=args.version.strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', new):
        raise SystemExit('Expected version format N.N.N.N')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8')); old=str(manifest['version'])
    targets=[MANIFEST, ROOT/'custom_components/freshairiq/const.py', ROOT/'quality/quality_policy.json', ROOT/'package.json', ROOT/'README.md', ROOT/'quality/performance_baseline.json']
    targets += list((ROOT/'custom_components/freshairiq/frontend').glob('freshairiq-*.js'))
    # These tests describe the current release contract. Historical versions
    # other than the immediately previous current version remain untouched.
    targets += list((ROOT/'tests').glob('*.py'))
    changed=[]
    for p in targets:
        if not p.exists(): continue
        s=p.read_text(encoding='utf-8')
        if old not in s: continue
        p.write_text(s.replace(old,new),encoding='utf-8'); changed.append(str(p.relative_to(ROOT)))
    notes=ROOT/'docs'/'releases'/f'RELEASE_NOTES_{new}.md'
    notes.parent.mkdir(parents=True, exist_ok=True)
    if not notes.exists():
        notes.write_text(f'# FreshAirIQ {new}\n\n## Reliability Foundation v1\n\n- Release-Metadaten zentral synchronisiert.\n- Verhaltensbasierte Regression-Gates konsolidiert.\n- Release wird bei roten Pflichtprüfungen blockiert.\n',encoding='utf-8')
    print(f'FreshAirIQ version: {old} -> {new}')
    print(f'Updated files: {len(changed)}')
    return 0
if __name__=='__main__': raise SystemExit(main())
