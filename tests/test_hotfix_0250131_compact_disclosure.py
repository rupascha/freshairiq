from pathlib import Path

CARD = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_compact_recommendation_uses_inline_disclosure():
    assert 'data-compact-toggle="decision"' in CARD
    assert 'decisionReasons = (st.intelligent_recommendation?.reasons' in CARD
    assert 'data-info="decision"' in CARD

def test_compact_room_disclosure_uses_canonical_room_reasons():
    assert 'data-compact-toggle="room:${esc(r.key)}"' in CARD
    assert 'const rawReasons = (r.recommendation_reasons || []).filter(Boolean);' in CARD
    assert 'data-room="${esc(r.key)}"' in CARD

def test_compact_disclosure_is_overflow_safe_and_keyboard_accessible():
    assert 'overflow-wrap:anywhere' in CARD
    assert 'e.key === "Enter" || e.key === " "' in CARD
    assert 'aria-expanded="${expanded ? "true" : "false"}"' in CARD
