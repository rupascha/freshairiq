from pathlib import Path
import json
from tools.golden_scenario_replay import replay
ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=ROOT/'quality/golden_scenarios/core_recommendations.json'

def test_golden_scenario_schema_and_privacy_contract():
    data=json.loads(SCENARIOS.read_text(encoding='utf-8'))
    assert data['schema']==1
    assert len(data['scenarios']) >= 7
    raw=SCENARIOS.read_text(encoding='utf-8').lower()
    for forbidden in ('person.paul','person.lydia','notify.mobile_app','installation_id','token','password'):
        assert forbidden not in raw

def test_all_golden_scenarios_replay_without_mismatch():
    count, failures=replay(SCENARIOS)
    assert count >= 7
    assert failures == []

def test_single_scenario_can_be_replayed_for_support_triage():
    count, failures=replay(SCENARIOS,'all_sensors_invalid')
    assert count == 1
    assert failures == []
