from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]

def test_pure_logic_scope_is_fail_closed_and_line_based():
    cfg=(ROOT/'.coveragerc-pure').read_text(encoding='utf-8')
    assert 'branch = False' in cfg
    assert 'fail_under = 100' in cfg
    gate=(ROOT/'tools/pure_logic_scope_gate.py').read_text(encoding='utf-8')
    assert 'pure module incorrectly omitted from 100% scope' in gate
    assert 'HA/aiohttp adapter missing from omit scope' in gate
    proc=subprocess.run([sys.executable,'tools/pure_logic_scope_gate.py'],cwd=ROOT,capture_output=True,text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr

def test_coverage_gate_starts_before_pytest_and_verifies_denominator():
    gate=(ROOT/'tools/pure_logic_coverage_gate.py').read_text(encoding='utf-8')
    assert "'-m','coverage','run'" in gate
    assert 'missing pure modules:' in gate
    assert 'covered != total' in gate
