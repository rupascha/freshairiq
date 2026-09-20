"""Regression contracts for v0.25.0.41 passive-open UI hotfix."""

from custom_components.freshairiq.consolidation import stabilise_recommendation
from custom_components.freshairiq.decision_brain import build_unified_decision


def _bathroom(**overrides):
    room = {
        "key": "badezimmer",
        "name": "Badezimmer",
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": True,
        "action": "Close",
        "close_recommended": True,
        "moisture_source_active": False,
        "session_elapsed_min": 143.4,
        "temperature_change_c": -0.1,
        "delta_g_m3": 3.1,
        "forecast_5_min_temperature_change_c": -0.03,
        "humidity": 60,
        "surface_rh": 62,
        "potential_ml": 96,
        "realistic_potential_ml": 2,
    }
    room.update(overrides)
    return room


def test_passive_open_monitor_survives_decision_brain_without_closed_window_copy():
    rooms = {"badezimmer": _bathroom()}
    stable = stabilise_recommendation(
        {"kind": "close", "room_keys": ["badezimmer"]},
        rooms,
        {"max_duration_min": 20},
    )
    assert stable["kind"] == "okay"
    assert stable["status"] == "passive_open_monitor"

    out = build_unified_decision(stable, rooms, {})
    brain = out["decision_brain"]
    assert out["status"] == "passive_open_monitor"
    assert brain["decision_label"] == "DAUER-/KIPPLÜFTUNG"
    assert "Daueröffnung" in brain["headline"]
    assert "gekippt/offen" in brain["action_line"]
    assert "geschlossen lassen" not in brain["action_line"].lower()
    assert "geschlossen lassen" not in out["instruction"].lower()


def test_passive_open_monitor_exits_to_close_when_temperature_forecast_becomes_bad():
    rooms = {
        "badezimmer": _bathroom(
            forecast_5_min_temperature_change_c=-0.8,
            efficiency_ml_per_01c=1.0,
        )
    }
    stable = stabilise_recommendation(
        {"kind": "close", "room_keys": ["badezimmer"]},
        rooms,
        {
            "max_duration_min": 20,
            "max_temp_loss_next_5_min_c": 0.6,
            "min_efficiency_ml_per_01c": 8,
        },
    )
    assert stable["kind"] == "close"
    assert stable.get("status") != "passive_open_monitor"


def test_passive_open_monitor_exits_to_close_when_reference_air_turns_too_moist():
    rooms = {"badezimmer": _bathroom(delta_g_m3=-0.5)}
    stable = stabilise_recommendation(
        {"kind": "close", "room_keys": ["badezimmer"]},
        rooms,
        {"max_duration_min": 20},
    )
    assert stable["kind"] == "close"
    assert stable.get("status") != "passive_open_monitor"


def test_frontend_has_dedicated_passive_open_presentation():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    js = (root / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert 'passiveOpenMonitor' in js
    assert 'mdi:window-open' in js
    assert 'DAUER-/KIPPLÜFTUNG' in js
    assert '<span>DAUERÖFFNUNG</span><b>wird überwacht</b>' in js
    assert 'DAUER-/KIPPLÜFTUNG WIRD ÜBERWACHT' in js
    assert 'passiveOpenRoom' in js
    assert 'Daueröffnung überwachen' in js


def test_passive_open_monitor_is_not_overridden_by_night_strategy():
    """A real long-open room remains authoritative over an unrelated night plan."""
    rooms = {
        "badezimmer": _bathroom(),
        "wohnkueche": _bathroom(
            key="wohnkueche", name="Wohnküche", active=False, action="Hold",
            close_recommended=False, session_elapsed_min=0,
        ),
    }
    stable = stabilise_recommendation(
        {"kind": "close", "room_keys": ["badezimmer"]},
        rooms,
        {"max_duration_min": 20},
    )
    night = {
        "active": True,
        "action": "pre_ventilate",
        "label": "NACHT · VORHER LÜFTEN",
        "headline": "Trockene Nachtluft nutzen, aber nicht dauerhaft",
        "instruction": "Vor dem Schlafengehen Wohnküche etwa 10 Minuten stoßlüften und danach schließen",
        "selected_rooms": ["Wohnküche"],
        "reasons": ["Nachtluft ist trockener"],
        "confidence": 80,
    }
    out = build_unified_decision(stable, rooms, {}, night_strategy=night)
    brain = out["decision_brain"]
    assert out["status"] == "passive_open_monitor"
    assert brain["night_strategy_primary"] is False
    assert brain["decision_label"] == "DAUER-/KIPPLÜFTUNG"
    assert "Daueröffnung" in brain["headline"]
    assert "Wohnküche" not in brain["action_line"]
