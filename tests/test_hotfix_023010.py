"""Regression tests for FreshAirIQ 0.25.0.7 opening-level strategy."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from custom_components.freshairiq.opening_strategy import enrich_opening_recommendation

ROOT = Path(__file__).resolve().parents[1]


def _opening(entity: str, name: str, *, delta: float, effect: float, temp: float = -0.2,
             candidate: bool = True, opened: bool = False, local: bool = False) -> dict:
    return {
        "entity_id": entity,
        "name": name,
        "available": True,
        "is_open": opened,
        "delta_g_m3": delta,
        "moisture_effect_next_5_min_ml": effect,
        "temperature_effect_next_5_min_c": temp,
        "airflow_factor": 1.0,
        "ventilation_candidate": candidate,
        "cooling_candidate": False,
        "source_label": "lokale Referenz" if local else "Außen-/Raumreferenz",
    }


def test_prefers_outside_windows_over_worse_wintergarden_door():
    rooms = {
        "wohnkueche": {
            "key": "wohnkueche",
            "name": "Wohnküche",
            "opening_assessments": [
                _opening("binary_sensor.fenster_sued", "Fenster Süd", delta=3.2, effect=58),
                _opening("binary_sensor.fenster_west", "Fenster West", delta=3.0, effect=55),
                _opening("binary_sensor.tuer_wintergarten", "Tür Wintergarten", delta=0.4, effect=7, candidate=False, local=True),
            ],
        }
    }
    rec = {
        "kind": "ventilate", "status": "ventilate", "title": "Jetzt lüften",
        "instruction": "Wohnküche lüften", "reasons": ["Raumluftfeuchte ist zu hoch"],
        "room_keys": ["wohnkueche"],
        "decision_brain": {"action_line": "Wohnküche lüften", "why": ["Raumluftfeuchte ist zu hoch"]},
    }
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"operating_profile": "comfort"})
    assert "Fenster Süd" in out["instruction"]
    assert "Fenster West" in out["instruction"]
    assert "Tür Wintergarten" in out["instruction"]
    assert "geschlossen lassen" in out["instruction"]
    assert out["decision_brain"]["action_line"] == out["instruction"]
    assert out["kind"] == "ventilate"
    assert out["status"] == "ventilate"


def test_running_session_closes_bad_local_opening_but_keeps_good_path():
    rooms = {
        "wohnkueche": {
            "key": "wohnkueche", "name": "Wohnküche", "active": True,
            "opening_assessments": [
                _opening("binary_sensor.fenster", "Außenfenster", delta=2.8, effect=46, opened=True),
                _opening("binary_sensor.tuer", "Wintergartentür", delta=-0.6, effect=-10, candidate=False, opened=True, local=True),
            ],
        }
    }
    rec = {
        "kind": "continue", "status": "ventilation_running", "title": "Weiterlüften",
        "instruction": "Wohnküche offen lassen", "reasons": [], "room_keys": ["wohnkueche"],
        "decision_brain": {"action_line": "Wohnküche offen lassen", "why": []},
    }
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"operating_profile": "comfort"})
    assert "Außenfenster offen lassen" in out["instruction"]
    assert "Wintergartentür schließen" in out["instruction"]
    assert out["kind"] == "continue"
    assert out["status"] == "ventilation_running"


def test_overlay_does_not_change_physical_forecast_or_room_selection():
    rooms = {"r": {"key": "r", "name": "Raum", "opening_assessments": [_opening("binary_sensor.f", "Fenster", delta=2.5, effect=30)]}}
    rec = {
        "kind": "ventilate", "status": "ventilate", "room_keys": ["r"],
        "forecast_confidence": 82, "expected_temperature_change_c": -0.4,
        "estimated_removed_ml": 120, "estimated_reheat_cost": 0.03,
        "instruction": "Raum lüften", "reasons": [],
    }
    before = {k: deepcopy(rec[k]) for k in ("kind", "status", "room_keys", "forecast_confidence", "expected_temperature_change_c", "estimated_removed_ml", "estimated_reheat_cost")}
    out = enrich_opening_recommendation(rec, rooms, {"operating_profile": "comfort"})
    for key, value in before.items():
        assert out[key] == value


def test_no_opening_data_preserves_existing_recommendation():
    rec = {"kind": "ventilate", "status": "ventilate", "room_keys": ["r"], "instruction": "Raum lüften", "reasons": ["x"]}
    assert enrich_opening_recommendation(deepcopy(rec), {"r": {"name": "Raum"}}, {}) == rec


def test_coordinator_disables_outdoor_future_for_active_local_reference():
    text = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "active_contact_reference = any(" in text
    assert text.count("and not active_contact_reference") >= 3
    assert '"opening_assessments": opening_assessments' in text
    assert "enrich_opening_recommendation(" in text


def test_release_version():
    assert 'VERSION = "0.25.0.53"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.53"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.53";' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
