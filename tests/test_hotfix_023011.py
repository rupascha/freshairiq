"""Regression tests for FreshAirIQ 0.25.0.7 mixed-source correctness hotfix."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.opening_strategy import _opening_score, enrich_opening_recommendation

ROOT = Path(__file__).resolve().parents[1]


def _opening(entity: str, name: str, *, delta: float, effect: float, opened: bool,
             airflow: float = 1.0, local: bool = False) -> dict:
    return {
        "entity_id": entity,
        "name": name,
        "available": True,
        "is_open": opened,
        "delta_g_m3": delta,
        "moisture_effect_next_5_min_ml": effect,
        "temperature_effect_next_5_min_c": -0.2,
        "airflow_factor": airflow,
        "ventilation_candidate": effect > 0,
        "cooling_candidate": False,
        "source_label": "lokale Referenz" if local else "Außen-/Raumreferenz",
    }


def test_close_from_bad_mixed_source_becomes_selective_continue():
    rooms = {
        "wohnkueche": {
            "key": "wohnkueche",
            "name": "Wohnküche",
            "active": True,
            # Canonical conservative room source is poor because the moistest
            # simultaneously open source is the winter-garden door.
            "delta_g_m3": -0.6,
            "opening_assessments": [
                _opening("binary_sensor.fenster", "Außenfenster", delta=2.8, effect=46, opened=True),
                _opening("binary_sensor.tuer", "Wintergartentür", delta=-0.6, effect=-10, opened=True, local=True),
            ],
        }
    }
    rec = {
        "kind": "close", "status": "close_windows", "title": "Jetzt schließen",
        "instruction": "Wohnküche schließen", "summary": "Ziel erreicht", "reasons": [],
        "room_keys": ["wohnkueche"],
        "decision_brain": {"action_line": "Wohnküche schließen", "why": []},
    }
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"operating_profile": "comfort", "close_delta": 0.4})
    assert out["kind"] == "continue"
    assert out["status"] == "ventilation_running"
    assert out["canonical_kind"] == "close"
    assert "Außenfenster offen lassen" in out["instruction"]
    assert "Wintergartentür schließen" in out["instruction"]
    assert out["decision_brain"]["action_line"] == out["instruction"]
    assert out["decision_brain"]["headline"] == "Gezielt weiterlüften"
    assert out["decision_brain"]["summary"] == out["summary"]


def test_close_with_still_good_room_gradient_is_not_overridden():
    rooms = {
        "r": {
            "key": "r", "name": "Raum", "active": True, "delta_g_m3": 1.2,
            "opening_assessments": [
                _opening("binary_sensor.good", "Gutes Fenster", delta=2.8, effect=40, opened=True),
                _opening("binary_sensor.bad", "Schlechte Tür", delta=-0.2, effect=-4, opened=True, local=True),
            ],
        }
    }
    rec = {"kind": "close", "status": "close_windows", "instruction": "Raum schließen", "room_keys": ["r"], "reasons": []}
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"close_delta": 0.4})
    assert out == rec



def test_running_source_below_close_delta_is_selectively_closed_even_if_slightly_drier():
    rooms = {
        "r": {
            "key": "r", "name": "Raum", "active": True,
            "opening_assessments": [
                _opening("binary_sensor.good", "Außenfenster", delta=2.6, effect=40, opened=True),
                _opening("binary_sensor.weak", "Wintergartentür", delta=0.2, effect=3, opened=True, local=True),
            ],
        }
    }
    rec = {"kind": "continue", "status": "ventilation_running", "instruction": "Raum offen lassen", "room_keys": ["r"], "reasons": []}
    out = enrich_opening_recommendation(deepcopy(rec), rooms, {"close_delta": 0.4})
    assert "Außenfenster offen lassen" in out["instruction"]
    assert "Wintergartentür schließen" in out["instruction"]

def test_opening_score_does_not_apply_airflow_twice():
    base = _opening("a", "A", delta=2.0, effect=40, opened=False, airflow=0.6)
    windy = {**base, "entity_id": "b", "name": "B", "airflow_factor": 1.5}
    # The effect already contains the airflow influence from evaluate_room.
    # Equal physical effect therefore must get equal rank regardless of the raw
    # airflow metadata.
    assert _opening_score(base, "comfort") == _opening_score(windy, "comfort")


def _contact_reference_helper():
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    helper = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_contact_specific_reference")
    mini = ast.Module(body=[helper], type_ignores=[])
    ast.fix_missing_locations(mini)

    values = {}
    ns = {
        "HomeAssistant": object,
        "Any": object,
        "CONF_CONTACT_REFERENCE_TEMPERATURES": "contact_reference_temperatures",
        "CONF_CONTACT_REFERENCE_HUMIDITIES": "contact_reference_humidities",
        "_contact_ids": lambda room: list(room.get("contacts", [])),
        "_open_seconds": lambda hass, entity, now: 10.0 if entity in room_open else None,
        "_float_state": lambda hass, entity: values.get(entity),
        "absolute_humidity": lambda t, rh: t + rh / 100.0,
        "dt_util": SimpleNamespace(utcnow=lambda: object()),
    }
    room_open = set()
    exec(compile(mini, "<contact_reference>", "exec"), ns)
    return ns["_contact_specific_reference"], values, room_open


def test_unavailable_configured_local_reference_never_falls_back_to_outdoor():
    fn, values, room_open = _contact_reference_helper()
    room_open.update({"outside", "wintergarden"})
    values.update({"sensor.wg_temp": None, "sensor.wg_humidity": 70.0})
    room = {
        "contacts": ["outside", "wintergarden"],
        "contact_reference_temperatures": {"wintergarden": "sensor.wg_temp"},
        "contact_reference_humidities": {"wintergarden": "sensor.wg_humidity"},
    }
    te, he, tv, hv = fn(
        object(), room,
        default_temp_entity="sensor.outdoor_temp", default_humidity_entity="sensor.outdoor_humidity",
        default_temp=10.0, default_humidity=50.0,
    )
    assert (te, he) == ("sensor.wg_temp", "sensor.wg_humidity")
    assert tv is None and hv is None


def test_partial_local_reference_never_mixes_with_outdoor_pair():
    fn, values, room_open = _contact_reference_helper()
    room_open.add("wintergarden")
    values["sensor.wg_temp"] = 18.0
    room = {
        "contacts": ["wintergarden"],
        "contact_reference_temperatures": {"wintergarden": "sensor.wg_temp"},
        "contact_reference_humidities": {},
    }
    te, he, tv, hv = fn(
        object(), room,
        default_temp_entity="sensor.outdoor_temp", default_humidity_entity="sensor.outdoor_humidity",
        default_temp=10.0, default_humidity=50.0,
    )
    assert te == "sensor.wg_temp" and he is None
    assert tv is None and hv is None


def test_release_version_023011():
    assert 'VERSION = "0.25.0.70"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.70"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.70";' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
