from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

def test_contact_specific_reference_contract_is_present():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    settings = (COMP / "settings_api.py").read_text(encoding="utf-8")
    assert "CONF_CONTACT_REFERENCE_TEMPERATURES" in const
    assert "CONF_CONTACT_REFERENCE_HUMIDITIES" in const
    assert "def _contact_specific_reference" in coordinator
    assert "contact_te and contact_he" in coordinator
    assert "benötigt immer Temperatur und Luftfeuchtigkeit" in settings

def test_dashboard_no_longer_exposes_internal_score_fallback():
    js = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "<b>Score ${fmt(comparison.now_score" not in js
    assert "IQ lernt gerade den realen Luftaustausch" in js
    assert "Situation neu eingeschätzt: Etagenlüftung läuft" not in js  # backend wording only

def test_floor_reassessment_and_learning_frame_latch_exist():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert '"presentation_scope"] = "floor"' in coordinator
    assert '"Situation neu eingeschätzt: Etagenlüftung läuft"' in coordinator
    assert 'mem["session_last_eligible_ah"]' in coordinator
    assert 'mem["session_learning_started"]' in coordinator
