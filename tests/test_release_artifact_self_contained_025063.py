from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def test_release_quality_inputs_are_shipped():
    assert (ROOT/'.coveragerc-pure').is_file()
    assert 'fail_under = 100' in (ROOT/'.coveragerc-pure').read_text()
    assert (ROOT/'quality/quality_policy.json').is_file()
    assert (ROOT/'.github/workflows/quality.yml').is_file()

def test_approved_ui_contract_remains_mandatory():
    p=json.loads((ROOT/'quality/quality_policy.json').read_text())
    assert 'tests/test_ui_configuration_contract_025061.py' in p['robustness']['required_test_files']
