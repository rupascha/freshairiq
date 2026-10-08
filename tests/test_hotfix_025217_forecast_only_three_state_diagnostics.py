from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
CONSOLIDATION = (ROOT / "custom_components/freshairiq/consolidation.py").read_text(encoding="utf-8")
BRAIN = (ROOT / "custom_components/freshairiq/decision_brain.py").read_text(encoding="utf-8")


def test_three_state_never_changes_canonical_recommendation():
    assert "apply_three_state_recommendation" not in COORDINATOR
    assert "compare_three_state_modes" not in COORDINATOR
    assert "Kipplüftung empfohlen" not in COORDINATOR
    assert "Stoßlüftung empfohlen" not in COORDINATOR
    assert not (ROOT / "custom_components/freshairiq/three_state_strategy.py").exists()


def test_three_state_still_selects_specialist_forecast_model():
    assert 'opening_model_key = "cross" if cross and opening_mode == "open" else specialist_opening_mode' in COORDINATOR
    assert 'if opening_model and int(opening_model.get("samples", 0) or 0) > 0:' in COORDINATOR
    assert 'effective_learning_rate = float(opening_model.get("rate", effective_learning_rate))' in COORDINATOR


def test_three_state_still_learns_tilt_open_cross_independently():
    assert 'session_mode in {"open", "tilted", "cross"}' in COORDINATOR
    assert 'defaults = {"open": 0.03, "tilted": 0.015, "cross": 0.04}' in COORDINATOR
    assert 'opening_learning[session_mode]' in COORDINATOR


def test_binary_long_open_detection_is_preserved():
    assert "probable tilt/dauer-open" in CONSOLIDATION
    assert "Dauer- oder Kippöffnung" in CONSOLIDATION
    assert "lange, stabile Öffnung als wahrscheinliche Dauer- oder Kipplüftung" in BRAIN
    assert "wahrscheinliche Dauer- oder Kipplüftung" in CARD


def test_diagnostic_three_state_summary_contains_models_without_entity_ids():
    diagnostics = (ROOT / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert '"proven_contact_count"' in diagnostics
    assert '"active_specialist_model"' in diagnostics
    assert '"models": {"tilted": model("tilted"), "open": model("open"), "cross": model("cross")}' in diagnostics
    assert '"session_predicted_removed_ml"' in diagnostics
    assert '"session_prediction_confidence"' in diagnostics
    assert '"passage_patterns_learned"' in diagnostics
    # The summary may count entity-keyed structures locally, but never returns their keys.
    helper = diagnostics[diagnostics.index("def _three_state_learning_diagnostic"):diagnostics.index("def _pick", diagnostics.index("def _three_state_learning_diagnostic")) if diagnostics.find("def _pick", diagnostics.index("def _three_state_learning_diagnostic")+10) >= 0 else diagnostics.index("_TOP_LEVEL_KEYS") ]
    assert '"three_state_contacts":' not in helper
    assert '"passage_behavior":' not in helper

def test_diagnostics_records_include_three_state_learning_summary():
    diagnostics = (ROOT / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert 'room["three_state_learning"] = _three_state_learning_diagnostic(raw, stored_room)' in diagnostics
    assert 'compact["three_state_learning"] = _three_state_learning_diagnostic(room_map.get(str(key), {}), raw)' in diagnostics
    assert diagnostics.count('three_state_learning"] = _three_state_learning_diagnostic') == 2


def test_no_schema_bump_for_additive_diagnostic_fields():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert 'DIAGNOSTICS_SCHEMA_VERSION = 15' in const
