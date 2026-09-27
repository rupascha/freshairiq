from pathlib import Path
CARD = (Path(__file__).parents[1] / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_passive_open_monitor_has_distinct_gentle_ventilation_state():
    assert 'status === "passive_open_monitor"' in CARD
    assert '"continuous"' in CARD
    assert 'faiqGentleVent' in CARD and 'faiqGentleFlow' in CARD

def test_active_ventilation_has_airflow_and_sailing_freshy():
    assert 'ai-airflow a' in CARD and 'ai-airflow b' in CARD and 'ai-airflow c' in CARD
    assert 'ai-air-leaf one' in CARD and 'ai-air-leaf two' in CARD
    assert 'faiqSailSmooth' in CARD

def test_new_animation_loops_explicitly_return_to_start_state():
    for name in ['faiqSailSmooth','faiqFlowA','faiqFlowB','faiqFlowC','faiqAirLeafA','faiqAirLeafB','faiqGentleVent','faiqGentleFlow','faiqGentleLeaf','faiqCoolFlow','faiqCelebrateSmooth','faiqZzzSmooth']:
        marker = f'@keyframes {name}'
        assert marker in CARD
        body = CARD.split(marker, 1)[1].split('}', 1)[0]
        assert '0%,100%' in body
