import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DE = json.loads((ROOT / "custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))

SECTION_FIELDS = {
    "add_room": {
        "identity": ["name", "floor", "include_in_calculations"],
        "properties": ["moisture_sources", "ventilation_threshold_mode", "ventilation_threshold_percent", "ventilation_threshold_ml"],
        "sensors": ["temperature", "humidity", "contacts", "contact_mode"],
        "geometry": ["volume", "length", "width", "height"],
        "optional_sensors": ["reference_temperature", "reference_humidity", "co2", "voc", "pm25", "illuminance"],
        "optional_actuators": ["climate", "exhaust_fan", "supply_fan", "ventilation_device", "dehumidifier", "humidifier", "air_purifier"],
    },
    "edit_room": {},
    "model": {
        "humidity_thresholds": ["start_rh", "high_rh", "target_rh", "min_delta", "min_delta_high_rh", "close_delta"],
        "recommendation_thresholds": ["min_potential_room_ml"],
        "ventilation_timing": ["min_duration_min", "max_duration_min", "post_ventilation_stabilization_min", "repeat_recommendation_cooldown_min", "repeat_min_benefit_ml"],
        "efficiency": ["min_return_next_5_min_ml", "max_temp_loss_next_5_min_c", "min_efficiency_ml_per_01c"],
        "health_limits": ["surface_factor", "mould_warn_surface_rh", "mould_critical_surface_rh", "co2_warn", "co2_critical"],
        "learning": ["learning_enabled", "learning_max_duration_min"],
    },
    "residents": {
        "residents": ["adult_occupants", "adult_resident_names", "adult_presence_entities", "child_occupants", "child_resident_names", "child_presence_entities", "pets_in_household"],
        "presence": ["presence_sensor_entities", "pet_safe_presence_entities", "untracked_follow_household"],
        "personalisation": ["personalisation_enabled", "thermal_preference", "personal_priority", "night_window_preference"],
        "night": ["night_start_hour", "night_end_hour", "night_forecast_enabled"],
        "resident_profiles": ["resident_room_profiles"],
    },
}
SECTION_FIELDS["edit_room"] = SECTION_FIELDS["add_room"]


def test_reported_resident_fields_are_translated_inside_section():
    residents = DE["options"]["step"]["residents"]["section"]["residents"]
    assert residents["data"]["adult_occupants"].startswith("Erwachsene")
    assert residents["data"]["adult_resident_names"].startswith("Namen Erwachsene")
    assert residents["data"]["adult_presence_entities"].startswith("Tracker Erwachsene")


def test_sectioned_forms_have_nested_german_field_translations():
    steps = DE["options"]["step"]
    for step_id, sections in SECTION_FIELDS.items():
        step = steps[step_id]
        assert "section" in step
        for section_id, fields in sections.items():
            sec = step["section"][section_id]
            for field in fields:
                label = sec["data"].get(field, "")
                description = sec["data_description"].get(field, "")
                assert label and label != field, (step_id, section_id, field)
                assert "Standard:" not in description, (step_id, section_id, field)
                assert ("Beispiel:" not in description) or field in {"cross_ventilation_pairs", "cross_zone_connections", "resident_room_profiles"}, (step_id, section_id, field)


def test_every_german_config_and_options_field_has_help_default_example():
    for area in ("config", "options"):
        for step_id, step in DE.get(area, {}).get("step", {}).items():
            for field, label in step.get("data", {}).items():
                assert label and label != field, (area, step_id, field)
                desc = step.get("data_description", {}).get(field, "")
                assert desc, (area, step_id, field)
                assert "Standard:" not in desc, (area, step_id, field)
                assert ("Beispiel:" not in desc) or field in {"cross_ventilation_pairs", "cross_zone_connections", "resident_room_profiles"}, (area, step_id, field)
