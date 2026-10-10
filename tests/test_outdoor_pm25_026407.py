"""0.26.4.7: outdoor fine-dust protection (user feedback "Luftsensor draußen", Sensor.Community)."""
from __future__ import annotations

import json
from pathlib import Path

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.decision_brain import build_unified_decision
from custom_components.freshairiq.language_confidence import adapt_language_confidence
from custom_components.freshairiq.localize import Translator, _german_score
from custom_components.freshairiq.model import RoomInput, evaluate_room
from custom_components.freshairiq.outdoor_air import (
    DEFAULT_OUTDOOR_PM25_MAX,
    outdoor_pm25_blocked,
    outdoor_pm25_limit,
    plausible_pm25,
    pm25_reason,
    veto_cause,
)
from custom_components.freshairiq.recommendation import build_recommendation

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"


def _opts(**extra):
    opts = dict(DEFAULT_OPTIONS)
    opts.update(extra)
    return opts


def test_rule_needs_a_plausible_reading_above_the_limit():
    assert DEFAULT_OUTDOOR_PM25_MAX == 35.0 == DEFAULT_OPTIONS["outdoor_pm25_max"]
    assert DEFAULT_OPTIONS["outdoor_pm25_enabled"] is True
    assert outdoor_pm25_blocked(_opts(), None) is False  # no sensor -> never blocks
    assert outdoor_pm25_blocked(_opts(), 35.0) is False
    assert outdoor_pm25_blocked(_opts(), 35.1) is True
    assert outdoor_pm25_blocked(_opts(outdoor_pm25_enabled=False), 200) is False
    assert outdoor_pm25_blocked(_opts(outdoor_pm25_max=20), 25) is True
    for broken in ("unavailable", float("nan"), -3, 5000):
        assert plausible_pm25(broken) is None and outdoor_pm25_blocked(_opts(), broken) is False
    assert outdoor_pm25_limit(_opts(outdoor_pm25_max="x")) == 35.0
    assert veto_cause(False, False) is None and veto_cause(True, False) == "pollen"
    assert veto_cause(False, True) == "pm25" and veto_cause(True, True) == "pollen_and_pm25"
    assert pm25_reason(48.4, _opts()) == "Feinstaub draußen (PM2.5) 48 µg/m³ liegt über dem eingestellten Grenzwert 35 µg/m³"


def _room(**extra):
    base = dict(key="wohnen", name="Wohnen", temperature=21.0, humidity=70.0, reference_temperature=8.0,
                reference_humidity=80.0, volume_m3=50.0, contact_open=False, contact_open_seconds=0.0)
    base.update(extra)
    return RoomInput(**base)


def test_room_model_postpones_normal_airing_but_not_critical_co2():
    clean = evaluate_room(_room(outdoor_pm25=12.0), _opts(), False)
    assert clean.action == "Ventilate"
    dusty = evaluate_room(_room(outdoor_pm25=80.0), _opts(), False)
    assert dusty.action == "Do not ventilate" and "fine dust" in dusty.reason
    critical = evaluate_room(_room(outdoor_pm25=80.0, co2=2000.0), _opts(), False)
    assert critical.action == "Ventilate"  # health first
    unknown = evaluate_room(_room(outdoor_pm25=None), _opts(), False)
    assert unknown.action == "Ventilate"


def _candidate(key="wohnen"):
    return {"key": key, "name": "Wohnen", "calculation_enabled": True, "data_quality": "ok", "active": False,
            "action": "Ventilate", "ventilation_candidate": True, "humidity": 70, "surface_rh": 70, "mould_level": "Elevated",
            "co2": None, "co2_available": False, "potential_ml": 400, "realistic_potential_ml": 400, "delta_g_m3": 4.0,
            "airflow_factor": 1, "forecast_temperature_change_c": -0.2, "temp_next_5_min_c": -0.2, "next_5_min_cost": 0,
            "forecast_cost": 0, "forecast_confidence": 80, "humidity_trend_pct_h": 0, "humidity_high_duration_min": 0}


def _build(**kw):
    return build_recommendation({"wohnen": _candidate()}, _opts(), threshold_ml=100, total_potential_ml=400,
                                recommended_duration_min=8, **kw)


def test_house_recommendation_names_fine_dust_as_the_reason():
    normal = _build()
    assert normal["kind"] == "ventilate"
    dusty = _build(outdoor_pm25=62.0, outdoor_pm25_blocked=True)
    assert dusty["kind"] == "pollen_wait" and dusty["status"] == "pollen_warning"
    assert dusty["outdoor_veto_cause"] == "pm25"
    assert "Feinstaubbelastung draußen" in dusty["summary"]
    assert any("Feinstaub draußen (PM2.5) 62 µg/m³" in r for r in dusty["reasons"])
    assert not any("Pollen" in r for r in dusty["reasons"])
    both = _build(outdoor_pm25=62.0, outdoor_pm25_blocked=True, pollen_blocked=True, pollen_index=5.0)
    assert both["outdoor_veto_cause"] == "pollen_and_pm25" and len(both["reasons"]) == 2
    pollen = _build(pollen_blocked=True, pollen_index=5.0)
    assert pollen["outdoor_veto_cause"] == "pollen" and "Pollenbelastung" in pollen["summary"]

    brain = build_unified_decision(dusty, {"wohnen": _candidate()}, _opts())
    assert brain["decision_brain"]["headline"] == "Lüften wäre sinnvoll – Feinstaub draußen spricht dagegen"
    worded = adapt_language_confidence(brain, {"wohnen": _candidate()}, {})
    assert "Feinstaub" in worded["decision_brain"]["headline"]
    translator = Translator({"Wohnen"})
    for text in (worded["decision_brain"]["headline"], dusty["summary"], *dusty["reasons"]):
        assert not _german_score(translator.text(text)), text


def test_moisture_source_headline_is_not_replaced_by_a_generic_airing_phrase():
    rec = {"kind": "ventilate", "status": "moisture_source_active", "title": "Dusche erkannt", "room_keys": ["bad"],
           "instruction": "Bad jetzt lüften", "duration_min": 5}
    rooms = {"bad": {"key": "bad", "name": "Bad", "delta_g_m3": 3.0, "potential_ml": 60}}
    out = adapt_language_confidence(build_unified_decision(rec, rooms, _opts()), rooms, {})
    assert out["decision_brain"]["headline"] == "Dusche erkannt"
    assert "Zeitpunkt" not in out["decision_brain"]["headline"]


def test_configuration_and_translations_offer_the_sensor_and_limit():
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    assert 'CONF_OUTDOOR_PM25_ENTITY, entity_ids(data.get(CONF_OUTDOOR_PM25_ENTITY))' in flow
    assert 'device_class="pm25", multiple=True' in flow
    assert 'native_option_key("outdoor_pm25_max")' in flow and 'native_option_key("outdoor_pm25_enabled")' in flow
    for name in ("translations/de.json", "translations/en.json", "strings.json"):
        data = json.loads((COMP / name).read_text(encoding="utf-8"))
        for step in (data["config"]["step"]["user"], data["config"]["step"]["reconfigure"], data["options"]["step"]["outdoor"]):
            assert step["data"]["outdoor_pm25_entity"] and step["data_description"]["outdoor_pm25_entity"]
        air = data["options"]["step"]["air_quality"]
        for key in ("outdoor_pm25_enabled", "outdoor_pm25_max"):
            assert air["data"][key] and air["data_description"][key]
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "entities.update(entity_ids(self.entry.data.get(CONF_OUTDOOR_PM25_ENTITY)))" in coordinator  # live updates
    assert '"outdoor_pm25_blocked": bool(self._outdoor_pm25_blocked)' in coordinator


def test_critical_paths_mention_fine_dust_and_edge_inputs_are_safe():
    from custom_components.freshairiq.house_decision import _mean_volume_factor
    from custom_components.freshairiq.intervention import build_interventions
    from custom_components.freshairiq.model import scaled_min_return

    co2_room = dict(_candidate("buero"), co2=2100, co2_available=True)
    mould_room = dict(_candidate("bad"), surface_rh=95, mould_level="Very high", delta_g_m3=3.0)
    for rooms in ({"buero": co2_room}, {"buero": co2_room, "bad": mould_room}, {"bad": mould_room}):
        out = build_recommendation(rooms, _opts(), threshold_ml=100, total_potential_ml=400, recommended_duration_min=8,
                                   outdoor_pm25=70.0, outdoor_pm25_blocked=True)
        assert out["kind"] in {"ventilate", "continue"}  # health first
        assert any("Feinstaub draußen 70 µg/m³" in r for r in out["reasons"]), out["reasons"]

    assert scaled_min_return("broken", 9.0) == 25.0 * 9.0 / 30.0
    assert _mean_volume_factor([]) == 1.0 and _mean_volume_factor(["broken", {"volume_m3": 15}]) == (1.0 + 0.5) / 2

    room = {"key": "r", "name": "R", "action": "Do not ventilate"}
    reasons = []
    for pollen, dust in ((True, True), (True, False), (False, True)):
        rows = build_interventions(room=dict(room, pollen_blocked=pollen, outdoor_pm25_blocked=dust),
                                   config={"air_purifier": "fan.purifier"}, options=_opts())
        reasons.append(next(r["reason"] for r in rows if r.get("entity_id") == "fan.purifier"))
    assert reasons == ["Außenluft ist durch Pollen und Feinstaub belastet.", "Außenluft ist pollenbedingt ungünstig.",
                       "Außenluft ist durch Feinstaub belastet."]
