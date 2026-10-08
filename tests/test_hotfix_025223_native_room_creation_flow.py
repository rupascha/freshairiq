"""Regression guards for v0.25.2.23 native HA room creation hotfix."""
from __future__ import annotations
from tests.release_version import CURRENT_RELEASE_VERSION
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")


def _add_flow() -> str:
    start = FLOW.index("class FreshAirIQRoomSubentryFlow")
    end = FLOW.index("    def _persist_room_update", start)
    return FLOW[start:end]


def test_native_add_uses_supported_per_contact_reference_contract():
    block = _add_flow()
    assert "_single_contact_reference_schema(room, contact)" in block
    assert "_apply_single_contact_reference(room, contact, user_input)" in block
    assert "_add_reference_contact_index" in block
    assert "_contact_reference_schema(room, self.hass)" not in block
    assert "_apply_contact_references(" not in block


def test_native_add_without_contacts_reaches_atomic_finalizer():
    block = _add_flow()
    no_contact_guard = block.index("if contacts and index < len(contacts):")
    finalizer = block.index("entry = self._get_entry()", no_contact_guard)
    create = block.index("return self.async_create_entry(", finalizer)
    assert no_contact_guard < finalizer < create
    assert "unique_id=unique_id" in block[create:]


def test_native_add_keeps_delay_values_before_reference_and_create():
    # 0.26.4.4: delay and orientation are entered on the per-opening page; that page
    # stores them (via _apply_single_contact_reference) before the room is created.
    block = _add_flow()
    apply = block.index("if _apply_single_contact_reference(room, contact, user_input):")
    finalizer = block.index("entry = self._get_entry()", apply)
    assert apply < finalizer
    helper = (COMP / "config_flow.py").read_text(encoding="utf-8")
    helper = helper[helper.index("def _apply_single_contact_reference("):]
    assert "delays[contact] = _safe_int(" in helper and "orientations[contact] = " in helper


def test_native_user_form_has_full_documented_section_parity_de_en():
    for filename in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((COMP / filename).read_text(encoding="utf-8"))
        steps = data["config_subentries"]["room"]["step"]
        user = steps["create_room"]
        basics = steps["room_basics"]
        assert set(user["data"]) == set(basics["data"])
        assert set(user["data_description"]) == set(basics["data_description"])
        assert set(user["sections"]) == set(basics["sections"])
        assert "optional_actuators" in user["sections"]
        for section_key, section in user["sections"].items():
            assert set(section.get("data", {})) == set(basics["sections"][section_key].get("data", {}))
            assert section.get("name") and section.get("description")
            assert set(section.get("data", {})) == set(section.get("data_description", {}))


def test_release_version_025223():
    manifest = json.loads((COMP / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == CURRENT_RELEASE_VERSION
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.2.23.md").is_file()
