"""Regression contract: native HA and dashboard are two views of one configuration."""
from __future__ import annotations
import ast
from pathlib import Path
from tests._source import module_source

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components/freshairiq"
FLOW=module_source("config_flow")
API=(COMP/"feedback_api.py").read_text(encoding="utf-8")
CARD=(COMP/"frontend/freshairiq-card.js").read_text(encoding="utf-8")

def _native_keys():
    tree=ast.parse((COMP/"settings_contract.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="NATIVE_OPTION_KEYS" for t in node.targets):
            value=node.value.args[0] if isinstance(node.value,ast.Call) else node.value
            return set(ast.literal_eval(value))
    raise AssertionError("NATIVE_OPTION_KEYS missing")

# test_every_native_global_option_is_exposed_by_dashboard: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_every_native_option_key_is_editable_on_a_native_form

# test_dashboard_cannot_create_dashboard_only_global_options: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_saving_native_pages_writes_only_contract_option_keys

def test_both_surfaces_use_same_configentry_option_store():
    # Dashboard writes entry.options and returns a freshly generated canonical payload.
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # Native flow also commits its working options into that same ConfigEntry.
    assert 'kwargs["options"] = new_options' in FLOW
    assert "self.hass.config_entries.async_update_entry(self.config_entry, **kwargs)" in FLOW

def test_dashboard_always_loads_fresh_canonical_state_when_settings_are_opened():
    assert "this._settingsData = null;" in CARD
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).

# test_base_data_surface_parity: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_outdoor_base_data_is_edited_natively_and_stored_in_entry_data

# test_room_core_fields_exist_on_both_surfaces: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services); intent now covered by ha_tests/test_retired_replacements_20261016.py::test_room_forms_expose_every_core_room_field

def test_per_contact_settings_share_same_room_storage():
    pairs={
        "contact_delays":"CONF_CONTACT_DELAYS",
        "contact_orientations":"CONF_CONTACT_ORIENTATIONS",
        "contact_reference_temperatures":"CONF_CONTACT_REFERENCE_TEMPERATURES",
        "contact_reference_humidities":"CONF_CONTACT_REFERENCE_HUMIDITIES",
        "contact_covers":"CONF_CONTACT_COVERS",
        "contact_passage_doors":"CONF_CONTACT_PASSAGE_DOORS",
    }
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    assert 'passage_doors[contact] = bool(user_input.get("passage_door", False))' in FLOW
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).

def test_room_changes_sync_parent_and_native_subentries_in_both_directions():
    # Dashboard -> parent + HA room subentry.
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # Native room editor -> parent + current subentry.
    assert "data[CONF_ROOMS] = rooms" in FLOW
    assert "self.hass.config_entries.async_update_subentry(" in FLOW
    # Native parent options flow -> all room subentries.
    assert "Keep native room subentries in lockstep with the canonical room data." in FLOW
