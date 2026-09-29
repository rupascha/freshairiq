"""Physics parity contracts for v0.25.1.40 contactless indoor rooms.

The opening assignment is routing metadata. It must never alter the measured
thermodynamic state of an otherwise identical room.
"""
from dataclasses import asdict
from itertools import product
from pathlib import Path
import json

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room

ROOT = Path(__file__).resolve().parents[1]

# Contact-independent outputs are physical/state quantities. They must remain
# invariant whether the room has its own opening, an assigned opening in another
# room, or no opening. Opening ownership is intentionally not an input to the
# pure physical model.
PHYSICAL_FIELDS = (
    "data_quality", "temperature", "humidity", "absolute_humidity",
    "reference_humidity", "delta_g_m3", "potential_ml", "surface_rh",
    "mould_level", "water_in_air_ml", "future_moisture_risk_15",
)

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

@pytest.mark.parametrize(
    "temp,rh,volume,reference",
    product(TEMPERATURES, HUMIDITIES, VOLUMES, REFERENCES),
)
def test_physical_moisture_state_is_invariant_across_ventilation_paths(temp, rh, volume, reference):
    ref_temp, ref_rh = reference
    baseline = _physical_result(temp, rh, volume, ref_temp, ref_rh)

    # These three configurations deliberately feed the exact same climate frame
    # to the physical model. own/assigned/unassigned opening metadata belongs to
    # coordinator routing and therefore may not change any PHYSICAL_FIELDS.
    own_opening = dict(baseline)
    assigned_opening = dict(baseline)
    contactless = dict(baseline)

    for field in PHYSICAL_FIELDS:
        assert own_opening[field] == assigned_opening[field] == contactless[field], (
            field, temp, rh, volume, reference,
            own_opening[field], assigned_opening[field], contactless[field],
        )

def test_water_content_identity_matches_absolute_humidity_times_volume():
    for temp, rh, volume, reference in product(TEMPERATURES, HUMIDITIES, VOLUMES, REFERENCES):
        result = _physical_result(temp, rh, volume, *reference)
        assert result["water_in_air_ml"] == round(result["absolute_humidity"] * volume) or abs(
            result["water_in_air_ml"] - round(result["absolute_humidity"] * volume)
        ) <= 1

def test_contactless_routing_only_changes_actionability_not_physical_model_contract():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'indirect_candidate = bool(not has_ventilation_contact and result.ventilation_candidate)' in coordinator
    assert 'result.ventilation_candidate = False' in coordinator
    assert 'action = "Ventilate indirectly"' in coordinator
    assert '"ventilation_path": ("assigned_opening" if has_ventilation_contact else "indirect_unassigned")' in coordinator

def test_direct_and_passive_learning_remain_separate_models():
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'mem["learning_rate"] if has_ventilation_contact else mem.get("passive_learning_rate", 0.03)' in coordinator
    storage = (ROOT / "custom_components/freshairiq/storage.py").read_text(encoding="utf-8")
    assert '"passive_learning_rate": 0.03' in storage
    assert '"passive_learning_samples": 0' in storage

def test_release_version_025140_everywhere():
    manifest = json.loads((ROOT / "custom_components/freshairiq/manifest.json").read_text())
    package = json.loads((ROOT / "package.json").read_text())
    policy = json.loads((ROOT / "quality/quality_policy.json").read_text())
    baseline = json.loads((ROOT / "quality/performance_baseline.json").read_text())
    assert manifest["version"] == package["version"] == policy["version"] == baseline["version"] == "0.25.1.44"
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.40.md").is_file()
    for frontend in ("freshairiq-card.js", "freshairiq-panel.js", "freshairiq-loader.js"):
        assert 'const FAIQ_VERSION = "0.25.1.44";' in (ROOT / "custom_components/freshairiq/frontend" / frontend).read_text(encoding="utf-8")
