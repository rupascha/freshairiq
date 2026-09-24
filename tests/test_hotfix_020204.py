from pathlib import Path

from custom_components.freshairiq.passive_ventilation import evaluate_passive_ventilation

ROOT = Path(__file__).resolve().parents[1]


def test_passive_ventilation_detects_drying_toward_reference():
    result = evaluate_passive_ventilation(
        start_ah=12.0,
        current_ah=11.8,
        reference_ah=6.0,
        volume_m3=100.0,
        elapsed_min=5.0,
        connected=True,
        start_reference_ah=6.0,
        samples=[{"elapsed_min": 0.0, "ah": 12.0}, {"elapsed_min": 2.5, "ah": 11.9}],
    )
    assert result["active"] is True
    assert result["estimated_ml"] == 20.0
    assert 35 <= result["confidence"] <= 85


def test_passive_ventilation_detects_humidifying_toward_reference():
    result = evaluate_passive_ventilation(
        start_ah=8.0,
        current_ah=8.2,
        reference_ah=12.0,
        volume_m3=50.0,
        elapsed_min=5.0,
        connected=True,
        start_reference_ah=12.0,
        samples=[{"elapsed_min": 0.0, "ah": 8.0}, {"elapsed_min": 2.5, "ah": 8.1}],
    )
    assert result["active"] is True
    assert result["estimated_ml"] == -10.0


def test_passive_ventilation_rejects_unrelated_wrong_direction_drift():
    result = evaluate_passive_ventilation(
        start_ah=12.0,
        current_ah=12.2,
        reference_ah=6.0,
        volume_m3=100.0,
        elapsed_min=8.0,
        connected=True,
    )
    assert result["active"] is False
    assert result["reason"] == "wrong_direction"


def test_passive_ventilation_needs_time_and_signal():
    early = evaluate_passive_ventilation(
        start_ah=12.0, current_ah=11.8, reference_ah=6.0,
        volume_m3=100.0, elapsed_min=1.0, connected=True,
    )
    tiny = evaluate_passive_ventilation(
        start_ah=12.0, current_ah=11.99, reference_ah=6.0,
        volume_m3=100.0, elapsed_min=5.0, connected=True,
    )
    assert early["active"] is False
    assert early["reason"] == "warming_up"
    assert tiny["active"] is False
    assert tiny["reason"] == "below_noise_floor"


def test_passive_display_is_estimate_and_separate_from_house_balance():
    js = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'PASSIV MITGELÜFTET' in js
    assert '≈ ${m.text}' in js
    assert 'vent-passive' in js
    assert 'passive_ventilation_estimated_ml' in coordinator
    assert 'NOT added' in coordinator or 'NOT added'.lower() in coordinator.lower()


def test_release_version_020204_artifacts_preserved_and_current_release_advanced():
    assert (ROOT / "RELEASE_NOTES_0.20.2.4.md").exists()
    assert 'VERSION = "0.25.0.61"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.61"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.61";' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
