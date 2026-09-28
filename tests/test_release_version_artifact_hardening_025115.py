"""Regression guards for v0.25.1.19 release version/artifact hygiene hardening."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]

def test_all_release_version_sources_match_manifest():
    version = json.loads((ROOT/'custom_components/freshairiq/manifest.json').read_text())['version']
    assert version == '0.25.1.22'
    assert json.loads((ROOT/'package.json').read_text())['version'] == version
    lock = json.loads((ROOT/'package-lock.json').read_text())
    assert lock['version'] == version
    assert lock['packages']['']['version'] == version
    assert json.loads((ROOT/'quality/quality_policy.json').read_text())['version'] == version
    assert json.loads((ROOT/'quality/performance_baseline.json').read_text())['version'] == version
    assert f'VERSION = "{version}"' in (ROOT/'custom_components/freshairiq/const.py').read_text()
    for name in ('freshairiq-card.js','freshairiq-panel.js','freshairiq-loader.js'):
        assert f'const FAIQ_VERSION = "{version}";' in (ROOT/'custom_components/freshairiq/frontend'/name).read_text()
    assert (ROOT/'docs/releases'/f'RELEASE_NOTES_{version}.md').is_file()

def test_release_builder_and_gate_fail_closed_on_caches_and_version_drift():
    policy=json.loads((ROOT/'quality/quality_policy.json').read_text())['release']
    assert '__pycache__' in policy['forbidden_path_parts']
    assert '.pytest_cache' in policy['forbidden_path_parts']
    assert '.pyc' in policy['forbidden_suffixes']
    gate=(ROOT/'tools/github_release_gate.py').read_text()
    for token in ('package-lock.json','quality/performance_baseline.json','FORBIDDEN_PARTS','FORBIDDEN_SUFFIXES'):
        assert token in gate
    builder=(ROOT/'tools/build_release.py').read_text()
    assert 'github_release_gate.py' in builder and '--zip' in builder

def test_bump_tool_updates_all_authoritative_version_files_and_blocks_reuse():
    bump=(ROOT/'tools/bump_release_version.py').read_text()
    for token in ('package-lock.json','README_DE.md','README_EN.md','new_tuple < old_tuple','--allow-same'):
        assert token in bump

def test_release_workflow_requires_tag_version_match():
    workflow=(ROOT/'.github/workflows/release.yml').read_text()
    assert 'Verify tag matches project version' in workflow
    assert 'TAG_VERSION="${GITHUB_REF_NAME#v}"' in workflow
    assert 'does not match manifest' in workflow

def test_gitignore_blocks_generated_artifacts():
    ignore=(ROOT/'.gitignore').read_text()
    for token in ('__pycache__/','*.py[cod]','.pytest_cache/','quality_reports/','*.zip'):
        assert token in ignore

def test_bump_tool_never_mutates_tests_or_historical_fixtures():
    bump=(ROOT/'tools/bump_release_version.py').read_text()
    assert "AUTHORITATIVE_TARGETS" in bump
    assert "(ROOT/'tests').glob" not in bump
    assert 'tests/*.py' not in bump
    assert "ROOT / 'tests'" not in bump
    assert '.glob(' not in bump


def test_release_requires_pure_coverage_configuration():
    coverage = ROOT / '.coveragerc-pure'
    assert coverage.is_file()
    text = coverage.read_text(encoding='utf-8')
    assert 'fail_under = 100' in text
    gate = (ROOT/'tools/github_release_gate.py').read_text(encoding='utf-8')
    assert '".coveragerc-pure"' in gate
