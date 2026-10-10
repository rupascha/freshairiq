"""Canonical 100% pure-logic LINE coverage gate.

Coverage starts before pytest imports project modules. This prevents early imports
from silently disappearing from the denominator (a pytest-cov source-resolution
edge case that previously hid pure modules).
"""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'custom_components/freshairiq'
CFG=ROOT/'.coveragerc-pure'
ADAPTER_PREFIXES=('homeassistant','aiohttp')


def _adapter(path: Path) -> bool:
    tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    for node in ast.walk(tree):
        names=[]
        if isinstance(node,ast.Import): names=[a.name for a in node.names]
        elif isinstance(node,ast.ImportFrom): names=[node.module or '']
        if any(name.startswith(ADAPTER_PREFIXES) for name in names): return True
    return False


def main() -> int:
    report_dir=ROOT/'quality_reports'; report_dir.mkdir(exist_ok=True)
    data=report_dir/'.coverage-pure'; json_report=report_dir/'coverage-pure.json'
    for path in (data,json_report):
        path.unlink(missing_ok=True)
    env=os.environ.copy(); env['COVERAGE_FILE']=str(data); env['PYTHONDONTWRITEBYTECODE']='1'
    run=[sys.executable,'-m','coverage','run','--rcfile=.coveragerc-pure','-m','pytest','-q','-p','no:cacheprovider','tests']
    if subprocess.run(run,cwd=ROOT,env=env).returncode: return 1
    report=[sys.executable,'-m','coverage','report','--rcfile=.coveragerc-pure','--show-missing']
    if subprocess.run(report,cwd=ROOT,env=env).returncode: return 1
    make_json=[sys.executable,'-m','coverage','json','--rcfile=.coveragerc-pure','-o',str(json_report)]
    if subprocess.run(make_json,cwd=ROOT,env=env).returncode: return 1
    payload=json.loads(json_report.read_text(encoding='utf-8'))
    measured={Path(name).name for name in payload.get('files',{})}
    expected={p.name for p in COMP.glob('*.py') if not _adapter(p)}
    missing=sorted(expected-measured)
    unexpected=sorted(measured-expected)
    if missing or unexpected:
        print('Pure-logic denominator integrity: FAIL')
        if missing: print(' missing pure modules:', ', '.join(missing))
        if unexpected: print(' unexpected measured modules:', ', '.join(unexpected))
        return 1
    totals=payload.get('totals',{})
    percent=float(totals.get('percent_covered',0.0))
    covered=int(totals.get('covered_lines',0)); total=int(totals.get('num_statements',0))
    if percent < 100.0 or covered != total:
        print(f'Pure-logic line coverage: FAIL ({covered}/{total}, {percent:.2f}%)')
        return 1
    print(f'Pure-logic denominator integrity: PASS ({len(expected)} modules)')
    print(f'Pure-logic line coverage: PASS ({covered}/{total}, {percent:.2f}%)')
    return 0

if __name__=='__main__': raise SystemExit(main())
