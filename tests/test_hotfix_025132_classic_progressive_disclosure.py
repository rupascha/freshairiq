from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def classic_block():
    start = JS.index("    _intelligentPanel(st, rooms = []) {")
    end = JS.index("    _recommendationRows(rooms) {", start)
    return JS[start:end]


def test_classic_renderer_has_primary_progressive_disclosure():
    block = classic_block()
    assert '<details class="decision-more">' in block
    assert 'Mehr zur Entscheidung' in block
    assert 'WARUM DIESE ENTSCHEIDUNG?' in block
    assert '<p class="decision-summary">' in block
    # These details must live inside the closed disclosure instead of being unconditional siblings.
    assert block.index('<details class="decision-more">') < block.index('WARUM DIESE ENTSCHEIDUNG?')


def test_classic_renderer_has_per_room_disclosure_from_canonical_reasons():
    block = classic_block()
    assert '<details class="decision-goal-room decision-room-disclosure"' in block
    assert 'r.recommendation_reasons' in block
    assert 'WARUM DIESER RAUM?' in block
    assert 'data-room="${esc(r.key)}"' in block


def test_classic_typography_is_readable_and_mobile_safe():
    assert '.decision-main h2{font-size:20px;line-height:24px}' in JS
    assert '.decision-action{font-size:13px;line-height:17px}' in JS
    assert '.decision-more-content .decision-summary{font-size:11.5px;line-height:16px' in JS
    assert 'grid-template-columns:minmax(0,1fr) auto 20px' in JS
    assert 'overflow-wrap:anywhere' in JS


def test_classic_and_iq_renderers_remain_available():
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in JS
