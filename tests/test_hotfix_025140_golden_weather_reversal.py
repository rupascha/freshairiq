"""Golden-master and dynamic weather-reversal regression gates for v0.25.1.40."""
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room, update_learning

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests/fixtures/v025138_physics_golden_master.json").read_text(encoding="utf-8"))


def _room(t, rh, volume, ref_t, ref_rh, **kw):
    base = dict(key="room", name="Room", temperature=t, humidity=rh,
                reference_temperature=ref_t, reference_humidity=ref_rh,
                volume_m3=volume, contact_open=False, contact_open_seconds=0,
                learning_rate=0.03, learning_samples=4)
    base.update(kw)
    return RoomInput(**base)


def test_v025138_golden_master_has_provenance_and_full_matrix():
    assert GOLDEN["baseline_version"] == "0.25.1.38"
    assert GOLDEN["model_sha256"] == "f688ea524692974580d22371a2f4ac04d90915384fd3013ce2c76aad6c9e32e6"
    assert len(GOLDEN["cases"]) == 81


@pytest.mark.parametrize("case", GOLDEN["cases"])
def test_v025140_preserves_v025138_physics_golden_master(case):
    t, rh, volume, ref_t, ref_rh = case["input"]
    current = asdict(evaluate_room(_room(t, rh, volume, ref_t, ref_rh), DEFAULT_OPTIONS, False))
    assert {field: current[field] for field in GOLDEN["fields"]} == case["output"]


@pytest.mark.parametrize("path", ("own_opening", "assigned_opening", "contactless"))
def test_dynamic_weather_reversal_dry_to_wet_closes_and_reports_moisture_gain(path):
    # Opening ownership is routing metadata; all three paths feed the same climate frame.
    start_ah = absolute_humidity(22.0, 68.0)
    dry = evaluate_room(_room(22.0, 68.0, 50.0, 8.0, 55.0,
                              contact_open=True, contact_open_seconds=300,
                              session_active=True, session_elapsed_min=5.0,
                              session_start_ah=start_ah, session_start_temp=22.0,
                              session_fresh_measurements=2), DEFAULT_OPTIONS, False)
    wet = evaluate_room(_room(22.0, 68.0, 50.0, 26.0, 92.0,
                              contact_open=True, contact_open_seconds=600,
                              session_active=True, session_elapsed_min=10.0,
                              session_start_ah=start_ah, session_start_temp=22.0,
                              session_fresh_measurements=2), DEFAULT_OPTIONS, False)
    assert dry.delta_g_m3 > 0
    assert dry.moisture_effect_next_5_min_ml > 0
    assert wet.delta_g_m3 < 0
    assert wet.moisture_effect_next_5_min_ml < 0
    assert wet.close_recommended is True
    assert wet.action == "Close"


@pytest.mark.parametrize("path", ("own_opening", "assigned_opening", "contactless"))
def test_dynamic_weather_reversal_wet_to_dry_restores_drying_physics(path):
    wet = evaluate_room(_room(22.0, 68.0, 50.0, 26.0, 92.0), DEFAULT_OPTIONS, False)
    dry = evaluate_room(_room(22.0, 68.0, 50.0, 8.0, 55.0), DEFAULT_OPTIONS, False)
    assert wet.delta_g_m3 < 0 and wet.moisture_effect_next_5_min_ml < 0
    assert dry.delta_g_m3 > 0 and dry.moisture_effect_next_5_min_ml > 0
    assert wet.action == "Do not ventilate"
    assert dry.ventilation_candidate is True


def test_wet_reference_air_is_not_accepted_as_positive_learning_evidence():
    start = absolute_humidity(22.0, 68.0)
    wet_source = absolute_humidity(26.0, 92.0)
    rate, samples, diagnosis, learned = update_learning(
        old_rate=0.03, old_samples=4, elapsed_min=10.0,
        start_ah=start, end_ah=start - 0.5, source_ah=wet_source,
        learning_enabled=True,
    )
    assert learned is False
    assert rate == 0.03 and samples == 4
    assert "start delta" in diagnosis


def test_coordinator_stickily_invalidates_learning_after_reference_weather_reversal():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'mem["session_reference_moisture_reversal"] = True' in source
    assert 'learning_contaminated = source_contaminated or reference_moisture_reversal' in source
    assert 'feedback_processed = False if learning_contaminated else learn_outcome_feedback' in source
    assert '"reference_moisture_reversal": reference_moisture_reversal' in source
