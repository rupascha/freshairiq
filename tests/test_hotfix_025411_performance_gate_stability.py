from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def test_performance_gate_uses_long_control_window():
    source=(ROOT/'tools/performance_gate.py').read_text(encoding='utf-8')
    assert 'control_iterations = iterations * 1200' in source
    assert 'control_iterations = iterations * 12' not in source.replace('control_iterations = iterations * 1200', '')

def test_performance_thresholds_are_not_weakened():
    policy=json.loads((ROOT/'quality/quality_policy.json').read_text(encoding='utf-8'))
    assert policy['performance']['warning_regression_percent'] == 15.0
    assert policy['performance']['failure_regression_percent'] == 30.0
    assert policy['performance']['rounds'] == 11
