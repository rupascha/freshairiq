from pathlib import Path

CARD = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_dark_card_owns_light_foreground():
    assert "linear-gradient(135deg,rgba(22,29,38,.99),rgba(17,23,30,.99));color:#e9f0f4;" in CARD
    assert "linear-gradient(135deg,rgba(22,29,38,.99),rgba(17,23,30,.99));color:var(--primary-text-color,#f3f7fa);" not in CARD


def test_dark_dialog_owns_light_foreground():
    assert ".dialog{color:#e9f0f4" in CARD
    assert "box-shadow:0 30px 80px rgba(0,0,0,.55)}.dialog-head{" in CARD


def test_affected_controls_continue_to_inherit_surface_foreground():
    assert ".details-btn,.close{appearance:none" in CARD
    assert "background:rgba(255,255,255,.04);color:inherit;border-radius:10px" in CARD
    assert ".profile-option{text-align:left" in CARD
    assert "background:rgba(255,255,255,.04);padding:12px;color:inherit}" in CARD
    assert ".learning-now{width:100%" in CARD and "background:rgba(91,212,255,.045);color:inherit}" in CARD
    assert ".learning-area{appearance:none" in CARD and "border:1px solid rgba(255,255,255,.065);color:inherit}" in CARD


def test_existing_room_contrast_contract_remains_intact():
    assert ".room-title,.room-water strong,.room-value,.room-big,.breakdown-row b,.breakdown-row strong,.ai-room b,.decision-room-disclosure>summary span,.decision-more>summary>span:first-child{color:#e9f0f4}" in CARD
