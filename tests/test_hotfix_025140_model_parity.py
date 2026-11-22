"""Physics parity contracts for v0.25.1.40 contactless indoor rooms.

The opening assignment is routing metadata. It must never alter the measured
thermodynamic state of an otherwise identical room.
"""
from dataclasses import asdict
from itertools import product
from pathlib import Path
import json

from tests.release_version import CURRENT_RELEASE_VERSION

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room
from tests._source import module_source

ROOT = Path(__file__).resolve().parents[1]

TEMPERATURES = (16.0, 21.5, 27.0)
HUMIDITIES = (45.0, 62.0, 78.0)
VOLUMES = (12.0, 45.0, 110.0)
REFERENCES = ((5.0, 55.0), (18.0, 75.0), (28.0, 80.0))

def _physical_result(temp, rh, volume, ref_temp, ref_rh):
    room = RoomInput(
        key="room", name="Room", temperature=temp, humidity=rh,
        reference_temperature=ref_temp, reference_humidity=ref_rh,
        volume_m3=volume, contact_open=False, contact_open_seconds=0,
        learning_rate=0.03, learning_samples=4,
    )
    return asdict(evaluate_room(room, DEFAULT_OPTIONS, False))

# test_physical_moisture_state_is_invariant_across_ventilation_paths: retired — it compared three copies of one result;
# the physics reference is the 81-case golden master in test_hotfix_025140_golden_weather_reversal.py

def test_water_content_identity_matches_absolute_humidity_times_volume():
    for temp, rh, volume, reference in product(TEMPERATURES, HUMIDITIES, VOLUMES, REFERENCES):
        result = _physical_result(temp, rh, volume, *reference)
        assert result["water_in_air_ml"] == round(result["absolute_humidity"] * volume) or abs(
            result["water_in_air_ml"] - round(result["absolute_humidity"] * volume)
        ) <= 1

def test_contactless_routing_only_changes_actionability_not_physical_model_contract():
    coordinator = module_source("coordinator")
    assert 'indirect_candidate = bool(not has_ventilation_contact and result.ventilation_candidate)' in coordinator
    assert 'result.ventilation_candidate = False' in coordinator
    assert 'action = "Ventilate indirectly"' in coordinator
    assert '"ventilation_path": ("assigned_opening" if has_ventilation_contact else "indirect_unassigned")' in coordinator

def test_direct_and_passive_learning_remain_separate_models():
    coordinator = module_source("coordinator")
    assert 'mem["learning_rate"] if has_ventilation_contact else mem.get("passive_learning_rate", 0.03)' in coordinator
    storage = module_source("storage")
    assert '"passive_learning_rate": 0.03' in storage
    assert '"passive_learning_samples": 0' in storage

def test_release_version_025140_everywhere():
    manifest = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text())
    baseline = json.loads((ROOT / "quality/performance_baseline.json").read_text())
    assert manifest["version"] == package["version"] == policy["version"] == baseline["version"] == CURRENT_RELEASE_VERSION
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.40.md").is_file()
    for frontend in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert f'const FAIQ_VERSION = "{CURRENT_RELEASE_VERSION}";' in (ROOT / "custom_components/freshairiq/frontend" / frontend).read_text(encoding="utf-8")
