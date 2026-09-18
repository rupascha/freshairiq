"""Regression contracts for the focused 0.25.0.7 hotfix."""
from pathlib import Path

from custom_components.freshairiq.intelligence import learn_outcome_feedback
from custom_components.freshairiq.intervention import build_interventions

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_manual_trustworthy_ventilation_can_teach_forecast_model():
    room = {
        "session_recommendation_followed": False,
        "session_prediction_snapshot_valid": True,
        "session_prediction_learning_weight": 1.0,
        "session_predicted_removed_ml": 100.0,
        "session_predicted_temperature_change_c": -0.5,
        "outcome_feedback_samples": 0,
    }
    assert learn_outcome_feedback(room, 95.0, -0.45) is True
    assert room["outcome_feedback_samples"] == 1
    assert room["last_outcome_feedback_applied"] is True


def test_timestamp_quality_learning_weight_is_applied_to_feedback_alpha():
    intelligence = (COMP / "intelligence.py").read_text(encoding="utf-8")
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert 'base_alpha *= learning_weight' in intelligence
    assert 'activity_weight = float(session_quality.get("learning_weight", 0.0) or 0.0)' in coordinator
    assert 'mem["session_prediction_learning_weight"] = activity_weight if session_activity_eligible else 0.0' in coordinator


def test_shading_uses_per_contact_cover_mapping_before_legacy_room_list():
    items = build_interventions(
        room={"temperature": 27, "humidity": 50, "illuminance": 20000, "action": "Wait"},
        config={
            "contact_covers": {
                "binary_sensor.window_left": ["cover.left"],
                "binary_sensor.door": ["cover.door"],
            },
            "covers": ["cover.legacy_should_not_be_used"],
        },
        options={"shade_above_temp_c": 24, "shade_min_illuminance_lx": 10000},
    )
    ids = {item["entity_id"] for item in items if item["key"] == "shade"}
    assert ids == {"cover.left", "cover.door"}


def test_hotfix_contracts_are_wired_through_native_dashboard_and_runtime():
    const = (COMP / "const.py").read_text(encoding="utf-8")
    flow = (COMP / "config_flow.py").read_text(encoding="utf-8")
    settings = (COMP / "settings_api.py").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")

    assert 'CONF_CONTACT_COVERS = "contact_covers"' in const
    assert 'selector.EntitySelectorConfig(domain="cover", multiple=True)' in flow
    assert 'room-contact-covers' in card
    assert 'id="room-covers"' not in card
    assert '_sync_room_subentries(hass, entry, data[CONF_ROOMS])' in settings
    assert 'self._working_data = _normalise_legacy_entry_data(dict(self.config_entry.data))' in flow
    assert 'weather_override_allowed' in coordinator
    assert 'anti_flap_min' in coordinator
    assert 'end_learning_valid = session_activity_eligible' in coordinator
    assert 'end_room_learning_valid' not in coordinator
    assert 'shadow_learning_weight_accumulator' in (COMP / 'intelligence.py').read_text(encoding='utf-8')
