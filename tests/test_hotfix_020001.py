from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from custom_components.freshairiq.validation import (
    option_relationship_error,
    repair_option_relationships,
)
from custom_components.freshairiq.ventilation_result import (
    finalise_ventilation_group,
    include_ventilation_group_start,
    new_ventilation_group,
    update_session_cross_tracking,
)

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"


def test_cross_ventilation_is_accumulated_over_time_instead_of_sampled_at_close():
    start = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)
    mem = {
        "session_active": True,
        "session_cross_active": True,
        "session_cross_seconds": 0.0,
        "session_cross_last_update": start.isoformat(),
    }
    assert update_session_cross_tracking(mem, start + timedelta(minutes=7), False)
    assert mem["session_cross_seconds"] == 420.0
    assert mem["session_cross_active"] is False
    # The three-second close-confirmation window must not add cross-flow time.
    update_session_cross_tracking(mem, start + timedelta(minutes=7, seconds=3), False)
    assert mem["session_cross_seconds"] == 420.0


def test_house_result_can_move_start_back_to_first_physical_opening():
    delayed_start = datetime(2026, 9, 11, 8, 5, tzinfo=timezone.utc)
    physical_start = delayed_start - timedelta(minutes=5)
    end = delayed_start + timedelta(minutes=10)
    group = new_ventilation_group(delayed_start)
    assert include_ventilation_group_start(group, physical_start)
    group["sessions"] = [{
        "event_id": "room:1",
        "key": "room",
        "name": "Room",
        "started_at": delayed_start.isoformat(),
        "ended_at": end.isoformat(),
        "duration_min": 10,
        "removed_ml": 100,
        "energy_kwh": 0,
        "cost": 0,
        "cross_ventilation": False,
    }]
    result = finalise_ventilation_group(group, end)
    assert result is not None
    assert result["started_at"] == physical_start.isoformat()
    assert result["duration_min"] == 15.0


def test_relationship_validation_rejects_all_contradictory_model_orders():
    base = {
        "target_rh": 58, "start_rh": 62, "high_rh": 68,
        "close_delta": 0.4, "min_delta_high_rh": 1.5, "min_delta": 2.5,
        "min_duration_min": 3, "max_duration_min": 20,
        "mould_warn_surface_rh": 80, "mould_critical_surface_rh": 90,
        "co2_warn": 1000, "co2_critical": 1400,
    }
    cases = [
        ({"target_rh": 70}, "invalid_humidity_order"),
        ({"min_delta_high_rh": 3.0}, "invalid_delta_order"),
        ({"min_duration_min": 30, "max_duration_min": 3}, "invalid_duration_order"),
        ({"mould_warn_surface_rh": 90, "mould_critical_surface_rh": 90}, "invalid_mould_order"),
        ({"co2_warn": 1400, "co2_critical": 1400}, "invalid_co2_order"),
    ]
    for change, expected in cases:
        assert option_relationship_error({**base, **change}) == expected


def test_legacy_contradictions_are_repaired_to_safe_ordering():
    repaired = repair_option_relationships({
        "target_rh": 70, "start_rh": 60, "high_rh": 55,
        "close_delta": 2.5, "min_delta_high_rh": 2.0, "min_delta": 1.0,
        "min_duration_min": 30, "max_duration_min": 3,
        "mould_warn_surface_rh": 95, "mould_critical_surface_rh": 90,
        "co2_warn": 2500, "co2_critical": 1400,
    })
    assert repaired["target_rh"] <= repaired["start_rh"] <= repaired["high_rh"]
    assert repaired["close_delta"] <= repaired["min_delta_high_rh"] <= repaired["min_delta"]
    assert repaired["min_duration_min"] <= repaired["max_duration_min"]
    assert repaired["mould_warn_surface_rh"] < repaired["mould_critical_surface_rh"]
    assert repaired["co2_warn"] < repaired["co2_critical"]


def test_dashboard_room_contacts_update_detail_controls_without_saving_first():
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert '_settingsContactRows(contacts, room = {})' in card
    assert 'roomContacts.addEventListener("change"' in card
    assert 'rowsHost.innerHTML = this._settingsContactRows(contacts' in card
    assert 'id="settings-contact-rows"' in card


def _flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for key, child in value.items():
            out.update(_flatten(child, f"{prefix}.{key}" if prefix else key))
    else:
        out[prefix] = value
    return out


def test_english_translation_keeps_runtime_and_native_configuration_english():
    de_raw = json.loads((COMP / "translations" / "de.json").read_text(encoding="utf-8"))
    en_raw = json.loads((COMP / "translations" / "en.json").read_text(encoding="utf-8"))
    de = _flatten(de_raw)
    en = _flatten(en_raw)
    assert set(de) == set(en)
    placeholder = re.compile(r"\{[^{}]+\}")
    for key in de:
        if isinstance(de[key], str) and isinstance(en[key], str):
            assert set(placeholder.findall(de[key])) == set(placeholder.findall(en[key])), key

    # v0.25.0.55: native Home Assistant setup/options follow the frontend
    # locale again. English is the source/fallback language and German remains
    # a separate complete translation.
    strings = json.loads((COMP / "strings.json").read_text(encoding="utf-8"))
    for section in ("config", "options", "selector", "config_subentries"):
        assert strings[section] == en_raw[section]
    assert en_raw["config"] != de_raw["config"]

    german_markers = re.compile(r"[äöüÄÖÜß]|\b(?:Wähle|Lüftung|Schimmel|Räume|Fenster|Außen|Feuchte|Zurück|Einstellungen|Querlüftung|Lernen)\b", re.I)
    flow_prefixes = ("config.", "options.", "selector.", "config_subentries.")
    leftovers = {
        key: value
        for key, value in en.items()
        if isinstance(value, str)
        and not key.startswith(flow_prefixes)
        and german_markers.search(value)
    }
    assert leftovers == {}


def test_readme_and_runtime_versions_are_current():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    const = (COMP / "const.py").read_text(encoding="utf-8")
    manifest = (COMP / "manifest.json").read_text(encoding="utf-8")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    assert "Current release: 0.25.0.55" in readme
    assert 'VERSION = "0.25.0.55"' in const
    assert '"version": "0.25.0.55"' in manifest
    assert 'const FAIQ_VERSION = "0.25.0.55"' in card


def test_house_strategy_learning_waits_for_complete_house_group():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert "completed_house_sessions: list[dict[str, Any]] = []" in coordinator
    assert "self.store.data, completed_house_sessions, room_meta_for_house" in coordinator
    assert "self.store.data, completed_sessions, room_meta_for_house" not in coordinator


def test_cross_ventilation_aggregate_is_labelled_as_room_minutes_not_wall_clock_minutes():
    start = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    group = new_ventilation_group(start)
    group["sessions"] = [
        {"event_id":"a","key":"a","name":"A","started_at":start.isoformat(),"ended_at":end.isoformat(),"duration_min":10,"removed_ml":100,"energy_kwh":0,"cost":0,"cross_ventilation":True,"cross_ventilation_minutes":8},
        {"event_id":"b","key":"b","name":"B","started_at":start.isoformat(),"ended_at":end.isoformat(),"duration_min":10,"removed_ml":100,"energy_kwh":0,"cost":0,"cross_ventilation":True,"cross_ventilation_minutes":8},
    ]
    result = finalise_ventilation_group(group, end)
    assert result is not None
    assert result["cross_ventilation_room_minutes_total"] == 16.0
    assert "cross_ventilation_minutes" not in result


def test_cross_ventilation_reopen_does_not_reapply_opening_delay_to_active_session():
    coordinator = (COMP / "coordinator.py").read_text(encoding="utf-8")
    assert 'active_session = bool((self.store.data.get("rooms", {}).get(key) or {}).get("session_active"))' in coordinator
    assert 'honour_delays=not active_session' in coordinator
