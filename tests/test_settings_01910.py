"""Regression checks for the v0.19.1.0 settings overhaul."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FLOW = ROOT / "custom_components/freshairiq/config_flow.py"
DE = ROOT / "custom_components/freshairiq/translations/de.json"
STRINGS = ROOT / "custom_components/freshairiq/strings.json"
CONST = ROOT / "custom_components/freshairiq/const.py"


def test_settings_are_grouped_and_have_explicit_back_navigation():
    text = CONFIG_FLOW.read_text(encoding="utf-8")
    assert '"ventilation_settings"' in text
    assert '"notification_energy_settings"' in text
    assert '"data_learning_settings"' in text
    assert '"back_to_main"' in text
    assert '"back_to_home_setup"' in text


def test_submitted_pages_persist_immediately():
    text = CONFIG_FLOW.read_text(encoding="utf-8")
    assert "def _persist_working_state" in text
    assert "async_update_entry(self.config_entry, **kwargs)" in text
    assert "async_schedule_reload(self.config_entry.entry_id)" in text
    assert "def _persist_room_update" in text
    # The model form contains sections and therefore must be flattened before saving.
    assert "submitted = _flatten_sections(user_input)" in text
    assert "self._working_options.update(submitted)" in text


def test_cross_ventilation_has_its_own_explained_page():
    data = json.loads(DE.read_text(encoding="utf-8"))
    step = data["options"]["step"]["cross_ventilation"]
    assert "wohnzimmer+schlafzimmer" in step["data_description"]["cross_ventilation_pairs"]
    assert "wohnzimmer+fitnessraum" in step["data_description"]["cross_zone_connections"]
    assert "{room_keys}" in step["description"]
    assert "Standard:" not in step["data"]["cross_ventilation_pairs"]


def test_moisture_sources_are_visible_in_german_room_settings():
    data = json.loads(DE.read_text(encoding="utf-8"))
    for step_name in ("add_room", "edit_room"):
        step = data["options"]["step"][step_name]
        assert "moisture_sources" in step["data"]
        assert "Standard:" not in step["data"]["moisture_sources"]
        assert "properties" in step["sections"]
    sub = data["config_subentries"]["room"]["step"]["room_basics"]
    assert "moisture_sources" in sub["data"]


def test_static_options_field_labels_do_not_repeat_defaults():
    data = json.loads(DE.read_text(encoding="utf-8"))["options"]["step"]
    for step in data.values():
        for label in step.get("data", {}).values():
            assert "Standard:" not in str(label)

def test_default_cross_zone_connections_exists():
    text = CONST.read_text(encoding="utf-8")
    assert '"cross_zone_connections": ""' in text


def test_source_strings_include_new_settings_keys():
    source = json.loads(STRINGS.read_text(encoding="utf-8"))
    steps = source["options"]["step"]
    for key in ("ventilation_settings", "cross_ventilation", "data_learning_settings"):
        assert key in steps
