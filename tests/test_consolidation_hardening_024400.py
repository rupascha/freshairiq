"""Final recommendation guard coverage and corruption tolerance."""
from custom_components.freshairiq.consolidation import stabilise_recommendation


def room(key="r", **kw):
    base = {
        "key": key,
        "name": key.title(),
        "floor": "ground_floor",
        "calculation_enabled": True,
        "data_quality": "ok",
        "active": False,
        "action": "Okay",
    }
    base.update(kw)
    return base


def test_stale_room_unknown_kind_and_nonfinite_metrics_are_normalised():
    out = stabilise_recommendation(
        {
            "kind": "made-up",
            "room_keys": ["missing"],
            "duration_min": float("nan"),
            "estimated_removed_ml": float("inf"),
            "estimated_reheat_cost": "broken",
            "forecast_confidence": 999,
            "expected_temperature_change_c": float("-inf"),
            "reasons": ["A", "A", "", "B"],
        },
        {"r": room()},
        {"min_duration_min": 3, "max_duration_min": 20},
    )
    assert out["kind"] == "okay"
    assert out["room_keys"] == []
    assert out["estimated_removed_ml"] == 0
    assert out["estimated_reheat_cost"] == 0
    assert out["forecast_confidence"] == 100
    assert out["expected_temperature_change_c"] == 0
    assert out["reasons"] == ["A", "B"]
    assert "unknown_kind_normalised" in out["consolidation_checks"]
    assert "stale_room_keys_removed" in out["consolidation_checks"]


def test_no_valid_room_forces_sensor_error():
    rooms = {"r": room(data_quality="unavailable")}
    out = stabilise_recommendation({"kind": "ventilate", "room_keys": ["r"]}, rooms, {})
    assert out["kind"] == "sensor"
    assert out["room_keys"] == []
    assert "no_valid_room_guard" in out["consolidation_checks"]


def test_long_stable_opening_enters_passive_monitor():
    rooms = {
        "r": room(
            active=True,
            action="Close",
            close_recommended=True,
            session_elapsed_min=45,
            temperature_change_c=-0.5,
            delta_g_m3=0.1,
            forecast_5_min_temperature_change_c=-0.2,
        )
    }
    out = stabilise_recommendation({"kind": "close", "room_keys": ["r"]}, rooms, {"max_duration_min": 20})
    assert out["kind"] == "okay"
    assert out["status"] == "passive_open_monitor"
    assert "long_open_monitor_mode" in out["consolidation_checks"]


def test_active_moisture_source_overrides_close():
    rooms = {
        "bath": room(
            "bath",
            active=True,
            action="Close",
            close_recommended=True,
            moisture_source_active=True,
            moisture_source_label="Dusche",
            delta_g_m3=2.0,
        )
    }
    out = stabilise_recommendation({"kind": "close", "room_keys": ["bath"]}, rooms, {"close_delta": 0.4})
    assert out["kind"] == "continue"
    assert "Dusche" in out["title"]
    assert "active_moisture_source_overrides_close" in out["consolidation_checks"]


def test_floor_scope_rebuilt_after_room_filtering():
    rooms = {
        "a": room("a", floor="basement"),
        "b": room("b", floor="basement"),
    }
    out = stabilise_recommendation({"kind": "ventilate", "room_keys": ["a", "b"], "duration_min": 8}, rooms, {})
    assert out["recommendation_scope"] == "floor"
    assert out["recommendation_floor"] == "basement"
    assert out["recommendation_floor_label"] == "Kellergeschoss"
    assert out["title"] == "Kellergeschoss lüften"
