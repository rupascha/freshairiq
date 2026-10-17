"""Support case (2026-10-17, IKEA VINDSTYRKA): a "VOC index" sensor has no unit
and no device class (Sensirion index 1–500, 100 = average). It must be
selectable and is rated against an index threshold, not against ppb/µg/m³.
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.intervention import VOC_INDEX_WARN, build_interventions, voc_scale


def test_scale_detection() -> None:
    assert voc_scale(None, None) == "index"
    assert voc_scale("", " ") == "index"
    assert voc_scale("volatile_organic_compounds", "µg/m³") == "concentration"
    assert voc_scale("volatile_organic_compounds_parts", "ppb") == "concentration"
    assert voc_scale(None, "ppb") == "concentration"  # unit-based sensor without device class
    assert VOC_INDEX_WARN == 250.0


def _purify(voc: float, scale: str | None) -> bool:
    room = {"key": "az", "name": "AZ", "action": "Okay", "humidity": 50, "temperature": 21, "voc": voc}
    if scale:
        room["voc_scale"] = scale
    rows = build_interventions(room=room, config={"air_purifier": "fan.purifier"}, options=dict(DEFAULT_OPTIONS))
    return any(row["key"] == "purify_air" for row in rows)


def test_index_sensor_uses_index_threshold() -> None:
    assert not _purify(106, "index")  # Frank's value: average air
    assert _purify(260, "index")
    # the same numbers on a concentration sensor keep the ppb/µg/m³ threshold (600)
    assert not _purify(260, "concentration")
    assert not _purify(260, None)
    assert _purify(650, "concentration")
