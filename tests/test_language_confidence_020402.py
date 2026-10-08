from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "custom_components/freshairiq/language_confidence.py"
spec = importlib.util.spec_from_file_location("faiq_language_confidence", MOD)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
adapt_language_confidence = module.adapt_language_confidence


def rec(kind="ventilate", confidence=80):
    return {
        "kind": kind, "room_keys": ["bed"], "duration_min": 8,
        "summary": "Etwa 8 Minuten sind sinnvoll.", "reasons": ["Außenluft ist trockener"],
        "decision_brain": {"summary": "Etwa 8 Minuten sind sinnvoll.", "why": ["Außenluft ist trockener"], "impact": {"confidence": confidence}},
    }


def room(samples=0, frame="excellent"):
    return {"learning_samples": samples, "forecast_observation_samples": samples,
            "outcome_feedback_samples": samples, "strategy_samples": samples,
            "behaviour_recommendation_opportunities": samples,
            "behaviour_duration_samples": samples,
            "forecast_confidence": 90, "measurement_frame_quality": frame}


def test_early_wording_is_cautious_and_physics_unchanged():
    source = rec()
    out = adapt_language_confidence(source, {"bed": room(0)}, {})
    assert "arbeitet hier noch überwiegend mit Gebäudephysik" in out["summary"]
    assert out["kind"] == source["kind"]
    assert out["room_keys"] == source["room_keys"]
    assert out["duration_min"] == source["duration_min"]
    assert out["language_confidence"]["maturity_band"] == "grundmodell"


def test_mature_wording_expresses_real_data_depth():
    out = adapt_language_confidence(rec(), {"bed": room(40)}, {})
    assert out["language_confidence"]["maturity_percent"] >= 50
    assert "unabhängige Beobachtungen bestätigen" in out["summary"]


def test_mature_model_can_still_be_situation_cautious():
    out = adapt_language_confidence(rec(confidence=35), {"bed": room(40, "uncertain")}, {})
    assert out["language_confidence"]["maturity_percent"] >= 50
    assert out["language_confidence"]["situation_confidence_percent"] < 65
    assert "bewusst" in out["summary"]


def test_close_action_keeps_action_summary_first():
    out = adapt_language_confidence(rec(kind="close"), {"bed": room(20)}, {})
    assert out["summary"].startswith("Etwa 8 Minuten sind sinnvoll.")


def test_layer_is_after_personal_context_and_before_sync():
    text = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert text.index("personalise_recommendation(") < text.index("adapt_language_confidence(") < text.index("sync_active_recommendation(")


def test_no_selected_rooms_uses_zero_maturity_without_changing_action():
    source = rec()
    out = adapt_language_confidence(source, {}, {})
    assert out["kind"] == source["kind"]
    assert out["room_keys"] == source["room_keys"]
    assert out["language_confidence"]["maturity_percent"] == 0
    assert out["language_confidence"]["evidence_samples"] == 0
