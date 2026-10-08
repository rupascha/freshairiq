from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

def test_contact_specific_reference_contract_is_present():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    settings = (COMP / "feedback_api.py").read_text(encoding="utf-8")
    assert "CONF_CONTACT_REFERENCE_TEMPERATURES" in const
    assert "CONF_CONTACT_REFERENCE_HUMIDITIES" in const
    assert "def _contact_specific_reference" in coordinator
    assert "contact_te and contact_he" in coordinator
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).

def test_dashboard_no_longer_exposes_internal_score_fallback():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "<b>Score ${fmt(comparison.now_score" not in js
    assert "IQ lernt gerade den realen Luftaustausch" in js
    assert "Situation neu eingeschätzt: Etagenlüftung läuft" not in js  # backend wording only

def test_floor_reassessment_and_learning_frame_latch_exist():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8") + (COMP / "house_decision.py").read_text(encoding="utf-8")  # rules moved in 0.26.3.2
    assert '"presentation_scope"] = "floor"' in coordinator
    assert '"Situation neu eingeschätzt: Etagenlüftung läuft"' in coordinator
    assert 'mem["session_last_eligible_ah"]' in coordinator
    assert 'mem["session_learning_started"]' in coordinator
