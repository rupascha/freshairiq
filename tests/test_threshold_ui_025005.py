from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js"


def test_threshold_detail_uses_local_mode_override_and_conditional_controls():
    text = CARD.read_text(encoding="utf-8")
    assert 'this._thresholdModeOverride || st.ventilation_threshold_mode || "adaptive_home_size"' in text
    assert 'mode === "percent_total_water"' in text
    assert 'id="threshold-percent-direct"' in text
    assert 'mode === "fixed_ml"' in text
    assert 'id="threshold-ml-direct"' in text
    assert 'const applyControl = mode === "adaptive_home_size" ? ""' in text


def test_threshold_apply_only_writes_active_value():
    text = CARD.read_text(encoding="utf-8")
    assert 'if (mode === "percent_total_water")' in text
    assert 'key:"min_potential_percent_total_water"' in text
    assert '} else if (mode === "fixed_ml")' in text
    assert 'key:"min_potential_total_ml"' in text
    assert 'key:"threshold_mode", value:mode' in text
