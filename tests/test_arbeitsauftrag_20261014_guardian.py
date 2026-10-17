"""F36: a working physics fallback after learning drift is not an invariant violation."""
from custom_components.freshairiq.guardian import evaluate_guardian


def _codes(learning_v2):
    return [f["code"] for f in evaluate_guardian({"learning_v2": learning_v2})["findings"]]


def test_drift_with_active_fallback_is_not_flagged():
    assert "FAIQ-GUARDIAN-LEARNING-001" not in _codes({"drift_detected": True, "physics_fallback_rooms": 2, "safety": {"learned_terms_allowed": False}})


def test_drift_without_protection_is_still_a_high_finding():
    assert "FAIQ-GUARDIAN-LEARNING-001" in _codes({"drift_detected": True, "safety": {"learned_terms_allowed": True}})
    assert "FAIQ-GUARDIAN-LEARNING-001" in _codes({"drift_detected": True})  # legacy payload without safety block
