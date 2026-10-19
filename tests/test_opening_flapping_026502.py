"""0.26.5.2 (community report): one bedroom window, outdoor air only slightly drier.

The notifications alternated every few minutes between "Gezielt weiterlüften.
Schlafzimmer: Fenster Schlafzimmer offen lassen · Fenster Schlafzimmer schließen"
and "Bitte Fenster schließen". The opening overlay put the only open window into
"keep open" and "close" at the same time and turned the house close into a
"keep ventilating". An opening is now never kept and closed at once; with a
single weak opening the close stays.
"""
from __future__ import annotations

from copy import deepcopy

from custom_components.freshairiq.opening_strategy import enrich_opening_recommendation

OPTIONS = {"operating_profile": "comfort", "close_delta": 0.4}


def _window(name="Fenster Schlafzimmer", entity="binary_sensor.schlaf_fenster", delta=0.3, effect=2.0, candidate=True):
    return {"entity_id": entity, "name": name, "available": True, "is_open": True, "delta_g_m3": delta,
            "moisture_effect_next_5_min_ml": effect, "temperature_effect_next_5_min_c": -0.2,
            "ventilation_candidate": candidate, "cooling_candidate": False}


def _close(room_keys=("schlaf",)):
    return {"kind": "close", "status": "close_windows", "title": "Schließen", "instruction": "Schlafzimmer schließen",
            "room_keys": list(room_keys), "reasons": []}


def test_single_weak_window_keeps_the_close() -> None:
    for delta, effect, candidate in ((0.3, 2.0, True), (0.4, 0.6, False), (0.1, 5.0, True)):
        rooms = {"schlaf": {"name": "Schlafzimmer", "active": True, "delta_g_m3": delta,
                            "opening_assessments": [_window(delta=delta, effect=effect, candidate=candidate)]}}
        out = enrich_opening_recommendation(deepcopy(_close()), rooms, OPTIONS)
        assert out["kind"] == "close" and out["status"] == "close_windows", (delta, effect)
        assert "offen lassen" not in out.get("instruction", "")
        assert "canonical_kind" not in out


def test_a_running_airing_never_names_one_window_twice() -> None:
    rooms = {"schlaf": {"name": "Schlafzimmer", "active": True, "opening_assessments": [_window()]}}
    rec = {"kind": "continue", "status": "ventilation_running", "instruction": "Schlafzimmer offen lassen", "room_keys": ["schlaf"], "reasons": []}
    out = enrich_opening_recommendation(deepcopy(rec), rooms, OPTIONS)
    assert "schließen" not in out.get("instruction", "")


def test_two_contacts_with_the_same_name_are_not_split() -> None:
    # e.g. a window with a tilt and an open contact, both called "Fenster Schlafzimmer"
    good = _window(entity="binary_sensor.schlaf_unten", delta=2.0, effect=25.0)
    weak = _window(entity="binary_sensor.schlaf_oben", delta=0.2, effect=0.8, candidate=False)
    rooms = {"schlaf": {"name": "Schlafzimmer", "active": True, "delta_g_m3": 0.3, "opening_assessments": [good, weak]}}
    out = enrich_opening_recommendation(deepcopy(_close()), rooms, OPTIONS)
    assert out["kind"] == "close" and "offen lassen" not in out.get("instruction", "")


def test_two_different_windows_still_get_a_route_change() -> None:
    good = _window(name="Fenster Garten", entity="binary_sensor.garten", delta=2.0, effect=25.0)
    bad = _window(name="Fenster Straße", entity="binary_sensor.strasse", delta=-0.3, effect=-4.0, candidate=False)
    rooms = {"schlaf": {"name": "Schlafzimmer", "active": True, "delta_g_m3": 0.3, "opening_assessments": [good, bad]}}
    out = enrich_opening_recommendation(deepcopy(_close()), rooms, OPTIONS)
    assert out["kind"] == "continue" and out["canonical_kind"] == "close"
    assert out["instruction"] == "Schlafzimmer: Fenster Garten offen lassen · Fenster Straße schließen"
