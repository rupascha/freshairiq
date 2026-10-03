"""Regression guards for v0.25.2.22 opening conflict and attic-apartment hotfix."""
from __future__ import annotations

from copy import deepcopy

from custom_components.freshairiq.const import PROPERTY_TYPES
from custom_components.freshairiq.forecast import _property_background_factor
from custom_components.freshairiq.opening_strategy import enrich_opening_recommendation


def test_single_open_cooling_candidate_is_never_told_open_and_close():
    opening = {
        "entity_id": "binary_sensor.sz_fenster", "name": "SZ-Fenster",
        "available": True, "is_open": True, "delta_g_m3": -0.4,
        "potential_ml": 0, "moisture_effect_next_5_min_ml": -2,
        "temperature_effect_next_5_min_c": -1.6,
        "ventilation_candidate": False, "cooling_candidate": True,
    }
    rooms = {"bedroom": {"name": "Schlafzimmer", "active": True, "delta_g_m3": -0.4, "opening_assessments": [opening]}}
    rec = {"kind": "close", "status": "close_windows", "title": "Schließen", "instruction": "Schlafzimmer schließen", "room_keys": ["bedroom"], "reasons": []}
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"operating_profile": "comfort", "close_delta": 0.4})
    assert out["kind"] == "close"
    assert out["status"] == "close_windows"
    assert "offen lassen" not in out.get("instruction", "")


def test_mixed_openings_still_keep_good_path_and_close_only_harmful_path():
    good = {"name":"Gut", "available":True, "is_open":True, "delta_g_m3":2.0, "moisture_effect_next_5_min_ml":30, "temperature_effect_next_5_min_c":-0.2, "ventilation_candidate":True, "cooling_candidate":False}
    bad = {"name":"Schlecht", "available":True, "is_open":True, "delta_g_m3":-0.5, "moisture_effect_next_5_min_ml":-8, "temperature_effect_next_5_min_c":-0.2, "ventilation_candidate":False, "cooling_candidate":False}
    rooms={"r":{"name":"Raum","active":True,"opening_assessments":[good,bad]}}
    rec={"kind":"continue","status":"ventilation_running","instruction":"Raum offen lassen","room_keys":["r"],"reasons":[]}
    out=enrich_opening_recommendation(rec, rooms, {"operating_profile":"comfort","close_delta":0.4})
    assert "Gut offen lassen" in out["instruction"]
    assert "Schlecht schließen" in out["instruction"]


def test_attic_apartment_is_supported_without_changing_existing_apartment_prior():
    assert "apartment" in PROPERTY_TYPES
    assert "attic_apartment" in PROPERTY_TYPES
    assert _property_background_factor({"property_type":"attic_apartment"}) == _property_background_factor({"property_type":"apartment"}) == 0.85
