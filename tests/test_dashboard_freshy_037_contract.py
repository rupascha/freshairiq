from pathlib import Path
CARD=Path('custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
def test_scope_is_typographic_not_scope_icon():
    assert '_presentationScope(brain, rooms)' in CARD
    assert 'class="decision-scope"' in CARD
    assert 'class="ai-scope"' in CARD
    assert 'mdi:home' not in CARD[CARD.index('_presentationScope'):CARD.index('_compactGoalChips')]
def test_freshy_compact_goal_chips_use_backend_goal_state():
    start=CARD.index('    _compactGoalChips(rooms) {')
    end=CARD.index('    _decisionGoalOverview(rooms) {', start)
    block=CARD[start:end]
    assert 'goal_state' in block
    assert 'humidity' in block and 'co2' in block and 'temperature' in block
    assert 'ai-goal-chip' in block
def test_sleepcap_is_real_cap_shape():
    assert '.ai-sleepcap:before' in CARD
    assert 'border-bottom:4px solid #dbe1ff' in CARD
    assert '.ai-sleepcap:after' in CARD
def test_existing_progressive_disclosure_preserved():
    assert 'data-compact-toggle="decision"' in CARD
    assert 'decision-more' in CARD
    assert 'data-classic-disclosure="decision"' in CARD
