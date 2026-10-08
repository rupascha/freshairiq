"""Atomically bump FreshAirIQ authoritative release metadata only.

Historical regression fixtures/tests are deliberately immutable. Version bumps may
only touch the explicit allow-list below; release gates verify the resulting state.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'custom_components/freshairiq/manifest.json'

# Explicit authoritative current-version sources. Never add tests, fixtures, release
# history or arbitrary globbed files here.
AUTHORITATIVE_TARGETS = (
    MANIFEST,
    ROOT / 'custom_components/freshairiq/const.py',
    ROOT / 'quality/quality_policy.json',
    ROOT / 'quality/performance_baseline.json',
    ROOT / 'package.json',
    ROOT / 'package-lock.json',
    ROOT / 'README.md',
    ROOT / 'README_DE.md',
    ROOT / 'README_EN.md',
    ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js',
    ROOT / 'custom_components/freshairiq/frontend/freshairiq-panel.js',
    ROOT / 'custom_components/freshairiq/frontend/freshairiq-loader.js',
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('version')
    ap.add_argument('--allow-same', action='store_true')
    args = ap.parse_args()
    new = args.version.strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', new):
        raise SystemExit('Expected version format N.N.N.N')

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    old = str(manifest['version'])
    old_tuple = tuple(map(int, old.split('.')))
    new_tuple = tuple(map(int, new.split('.')))
    if new_tuple < old_tuple or (new_tuple == old_tuple and not args.allow_same):
        raise SystemExit(
            f'New version must be greater than current version {old}; '
            'use --allow-same only for metadata repair'
        )

    changed = []
    for p in AUTHORITATIVE_TARGETS:
        if not p.exists():
            continue
        s = p.read_text(encoding='utf-8')
        if old not in s:
            continue
        p.write_text(s.replace(old, new), encoding='utf-8')
        changed.append(str(p.relative_to(ROOT)))

    notes = ROOT / 'docs' / 'releases' / f'RELEASE_NOTES_{new}.md'
    notes.parent.mkdir(parents=True, exist_ok=True)
    if not notes.exists():
        notes.write_text(
            f'# FreshAirIQ {new}\n\n## Reliability Foundation v1\n\n'
            '- Release-Metadaten zentral synchronisiert.\n'
            '- Verhaltensbasierte Regression-Gates konsolidiert.\n'
            '- Release wird bei roten Pflichtprüfungen blockiert.\n',
            encoding='utf-8',
        )
    print(f'FreshAirIQ version: {old} -> {new}')
    print(f'Updated files: {len(changed)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
