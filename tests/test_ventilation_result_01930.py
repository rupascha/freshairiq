from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.decision_brain import build_unified_decision
from custom_components.freshairiq.ventilation_result import (
    append_completed_sessions,
    finalise_ventilation_group,
    new_ventilation_group,
)

ROOT = Path(__file__).resolve().parents[1]


def _event(key, name, start, end, removed, *, duration=10, temp=-0.5, cost=0.1, predicted=100, order=0):
    return {
        "event_id": f"{key}:{start.isoformat()}:{end.isoformat()}",
        "key": key,
        "name": name,
        "floor": "ground_floor",
        "sort_order": order,
        "volume_m3": 50,
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "removed_ml": removed,
        "duration_min": duration,
        "temp_delta_c": temp,
        "energy_kwh": 0.25,
        "cost": cost,
        "cross_ventilation": True,
        "learning_valid": True,
        "moisture_source_contaminated": False,
        "recommendation_followed": True,
        "predicted_removed_ml": predicted,
        "predicted_temperature_change_c": -0.4,
        "prediction_comparable": True,
    }


def test_house_ventilation_result_spans_first_open_to_last_close_and_keeps_room_breakdown():
    start = datetime(2026, 9, 11, 7, 0, tzinfo=timezone.utc)
    mid = start + timedelta(minutes=8)
    end = start + timedelta(minutes=12)
    group = new_ventilation_group(start)
    assert append_completed_sessions(group, [
        _event("living", "Wohnzimmer", start, mid, 180, duration=8, predicted=160, order=1),
        _event("bath", "Badezimmer", start + timedelta(minutes=2), end, 120, duration=10, predicted=140, order=2),
    ])

    result = finalise_ventilation_group(group, end, display_minutes=5)
    assert result is not None
    assert result["removed_ml"] == 300
    assert result["duration_min"] == 12.0
    assert result["room_count"] == 2
    assert [r["name"] for r in result["room_results"]] == ["Wohnzimmer", "Badezimmer"]
    assert result["display_until"] == (end + timedelta(minutes=5)).isoformat()
    assert result["prediction_error_ml"] == 0
    assert result["prediction_accuracy_percent"] == 100
    assert result["cross_ventilation"] is True


def test_completed_room_events_are_not_duplicated_after_restart_save_cycle():
    start = datetime(2026, 9, 11, 7, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    event = _event("living", "Wohnzimmer", start, end, 100)
    group = new_ventilation_group(start)
    assert append_completed_sessions(group, [event]) is True
    assert append_completed_sessions(group, [event]) is False
    assert len(group["sessions"]) == 1


def test_decision_explanation_uses_ventilation_average_instead_of_hausmittel():
    rec = {
        "kind": "ventilate",
        "room_keys": ["living"],
        "duration_min": 10,
        "house_strategy": {"maturity": 50, "efficiency_factor": 1.11},
    }
    rooms = {
        "living": {
            "name": "Wohnzimmer",
            "humidity": 65,
            "surface_rh": 65,
            "delta_g_m3": 2.0,
            "realistic_potential_ml": 150,
        }
    }
    out = build_unified_decision(rec, rooms, {})
    why = " ".join(out["decision_brain"]["why"])
    assert "bisheriger Lüftungsdurchschnitt" in why
    assert "Hausmittel" not in why


def test_dashboard_contains_five_minute_result_and_persistent_last_ventilation_detail():
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    sensor = (ROOT / "custom_components/freshairiq/sensor.py").read_text()
    assert 'data-info="lastvent"' in card
    assert "display_until" in card
    assert "LÜFTUNG ABGESCHLOSSEN" in card
    assert "Vom Öffnen des ersten bis zum Schließen des letzten Lüftungsfensters" in card
    assert '"last_ventilation": self.coordinator.data.get("last_ventilation")' in sensor
