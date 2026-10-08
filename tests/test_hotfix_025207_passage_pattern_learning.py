from pathlib import Path
from custom_components.freshairiq.opening_state import update_passage_pattern


def test_passage_pattern_requires_repeated_evidence():
    stats = None
    for _ in range(2):
        stats = update_passage_pattern(stats, pulled_shut_evidence=True)
    assert stats["learned"] is False
    stats = update_passage_pattern(stats, pulled_shut_evidence=True)
    assert stats == {"pulled_shut_events": 3, "genuine_open_events": 0, "observations": 3, "confidence": 1.0, "learned": True}


def test_genuine_open_evidence_prevents_overeager_learning():
    stats = None
    for evidence in (True, False, True, False):
        stats = update_passage_pattern(stats, pulled_shut_evidence=evidence)
    assert stats["confidence"] == 0.5
    assert stats["learned"] is False


def test_learned_pattern_never_rewrites_contact_state():
    root = Path(__file__).parents[1]
    opening = (root / "custom_components/freshairiq/opening_state.py").read_text(encoding="utf-8")
    coord = (root / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "It never rewrites" in opening
    assert "Sensorzustand wird nicht überschrieben" in coord
    assert '"passage_pattern_learned"' in coord
    assert '"passage_behavior"' in coord


def test_existing_binary_and_three_state_guards_remain_present():
    root = Path(__file__).parents[1]
    coord = (root / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    opening = (root / "custom_components/freshairiq/opening_state.py").read_text(encoding="utf-8")
    assert "stabilise_explicit_mode" in coord
    assert 'str(entity_id).startswith("binary_sensor.")' in opening
    assert "FAIQ-OPENING-3STATE-003" in coord
