from pathlib import Path
CARD=Path('custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_font_scale_uses_fixed_steps_and_selects():
    assert 'FAIQ_FONT_SCALE_STEPS = Object.freeze([0.8,0.9,1,1.1,1.2,1.3,1.4,1.5])' in CARD
    assert '<select class="scale-select" data-scale-key="${key}">' in CARD
    assert 'input type="range" min="0.8" max="1.5"' not in CARD
    assert 'festen 10-%-Stufen von 80 bis 150 %' in CARD

def test_100_percent_preserves_established_classic_baselines():
    expected=(
      '.decision-main h2{font-size:calc(22px * var(--faiq-font-recommendation,1));line-height:calc(27px * var(--faiq-font-recommendation,1))}',
      '.decision-action{font-size:calc(15px * var(--faiq-font-recommendation,1));line-height:calc(20px * var(--faiq-font-recommendation,1))}',
      '.decision-card>.decision-summary{font-size:calc(13px * var(--faiq-font-recommendation,1));line-height:calc(18px * var(--faiq-font-recommendation,1))}',
      '@media(max-width:520px){.decision-main h2{font-size:calc(21px * var(--faiq-font-recommendation,1));line-height:calc(26px * var(--faiq-font-recommendation,1))}',
    )
    for rule in expected: assert rule in CARD
    assert '.decision-main h2{font-size:calc(18px * var(--faiq-font-recommendation,1))' not in CARD

def test_scale_categories_are_scoped_not_global_tiny_muted_overrides():
    assert '.tiny,.muted,.hero,.pill,.ai-scope,.ai-goal-chip{font-size:calc(' not in CARD
    assert '.top .hero{font-size:calc(12px * var(--faiq-font-meta,1))' in CARD
    assert '.metrics .metric .tiny' in CARD
    assert '.decision-room-detail .decision-room-reason span' in CARD

def test_existing_cards_default_to_exact_100_percent():
    for key in ('recommendation','goals','rooms','metrics','details','meta'):
        assert f'font_scale_{key}: normalizeFontScale(raw.font_scale_{key})' in CARD
    assert 'if(!Number.isFinite(n)) return 1' in CARD
