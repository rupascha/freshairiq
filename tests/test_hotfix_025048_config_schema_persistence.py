"""Permanent contracts for the v0.25.0.48 German config-flow schema.

These checks intentionally protect the user-facing Devices & Services schema from
regressing to raw Home Assistant field keys or losing help/default/example text.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"

DE = json.loads((COMP / "translations" / "de.json").read_text(encoding="utf-8"))
EN = json.loads((COMP / "translations" / "en.json").read_text(encoding="utf-8"))
STRINGS = json.loads((COMP / "strings.json").read_text(encoding="utf-8"))


def _field_records(payload: dict) -> dict[tuple[str, ...], tuple[str, str]]:
    """Return every config/options form field with label + description."""
    result: dict[tuple[str, ...], tuple[str, str]] = {}
    for area in ("config", "options"):
        for step_id, step in payload.get(area, {}).get("step", {}).items():
            data = step.get("data", {})
            descriptions = step.get("data_description", {})
            for field, label in data.items():
                result[(area, step_id, "data", field)] = (
                    str(label or ""), str(descriptions.get(field, "") or "")
                )
            for section_id, section in step.get("section", {}).items():
                sec_data = section.get("data", {})
                sec_desc = section.get("data_description", {})
                for field, label in sec_data.items():
                    result[(area, step_id, "section", section_id, "data", field)] = (
                        str(label or ""), str(sec_desc.get(field, "") or "")
                    )
    return result


def test_german_devices_services_schema_never_falls_back_to_raw_keys():
    records = _field_records(DE)
    assert records, "No German config/options fields discovered"
    for path, (label, _description) in records.items():
        field = path[-1]
        assert label.strip(), path
        assert label.strip() != field, (path, label)
        # A raw snake_case identifier is the exact failure mode seen in HA.
        assert not ("_" in label and label.lower() == label and " " not in label), (path, label)


def test_every_german_setting_keeps_description_default_and_example():
    records = _field_records(DE)
    for path, (_label, description) in records.items():
        assert description.strip(), path
        assert "Standard:" not in description, (path, description)
        assert ("Beispiel:" not in description) or path[-1] in {"cross_ventilation_pairs", "cross_zone_connections", "resident_room_profiles"}, (path, description)


def test_translation_field_shapes_stay_in_lockstep():
    """Missing DE paths would make Home Assistant expose fallback/raw field names."""
    de_paths = set(_field_records(DE))
    en_paths = set(_field_records(EN))
    strings_paths = set(_field_records(STRINGS))
    assert de_paths == en_paths == strings_paths


def test_required_github_workflows_are_part_of_every_project_package():
    workflows = ROOT / ".github" / "workflows"
    required = {
        "quality.yml": "workflow_call:",
        "release.yml": 'tags:\n      - "v*"',
        "validate.yml": "workflow_dispatch:",
    }
    for filename, marker in required.items():
        path = workflows / filename
        assert path.is_file(), f"Missing mandatory workflow: {path}"
        text = path.read_text(encoding="utf-8")
        assert marker in text, (filename, marker)

    release = (workflows / "release.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/quality.yml" in release
    assert "freshairiq-clean-release" in release
    assert "gh release create" in release
