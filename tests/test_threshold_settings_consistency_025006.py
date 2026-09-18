from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / 'custom_components' / 'freshairiq'


def test_threshold_settings_are_guided_and_unambiguous():
    flow = (COMP / 'config_flow.py').read_text(encoding='utf-8')
    assert 'async def async_step_threshold(' in flow
    assert 'async def async_step_threshold_percent(' in flow
    assert 'async def async_step_threshold_fixed(' in flow
    model = flow[flow.index('def _model_schema'):flow.index('def _profile_schema') if 'def _profile_schema' in flow else flow.index('def _forecast_schema')]
    # The generic advanced-model form must not expose both house threshold values.
    assert 'min_potential_percent_total_water' not in model
    assert 'min_potential_total_ml' not in model


def test_automatic_threshold_explanation_matches_runtime_formula():
    js = (COMP / 'frontend' / 'freshairiq-card.js').read_text(encoding='utf-8')
    de = json.loads((COMP / 'translations' / 'de.json').read_text(encoding='utf-8'))
    desc = de['options']['step']['threshold']['description']
    for token in ('durch vier', '6–12 %', '25 %', '2 °C'):
        assert token in desc
    for token in ('durch vier', '6–12 %', '25 %', '2 °C'):
        assert token in js
