from pathlib import Path
import json, re
ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
CARD=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def block(start,end):
    a=FLOW.index(start); b=FLOW.index(end,a)
    return FLOW[a:b]

def test_first_screen_has_exactly_two_explicit_setup_paths_and_no_empty_shell():
    user=block("async def async_step_user","async def async_step_quick_start")
    assert 'async_show_menu' in user
    assert 'menu_options=["quick_start", "exact_outdoor"]' in user
    assert '"later"' not in user
    assert "async_create_entry" not in user

def test_quick_setup_requires_usable_outdoor_reference_before_room():
    quick=block("async def async_step_quick_start","async def async_step_reconfigure")
    assert "_quick_outdoor_configuration_error" in quick
    assert "async_step_quick_room()" in quick
    validator=block("def _quick_outdoor_configuration_error","def _outdoor_schema")
    assert '"outdoor_source_required"' in validator
    assert "CONF_OUTDOOR_WEATHER" in validator
    assert "CONF_OUTDOOR_TEMPERATURE" in validator and "CONF_OUTDOOR_HUMIDITY" in validator

def test_quick_room_is_minimum_viable_not_empty_or_fake_default():
    schema=block("def _quick_room_schema","def _quick_room_input")
    assert "vol.Required(CONF_ROOM_TEMPERATURE)" in schema
    assert "vol.Required(CONF_ROOM_HUMIDITY)" in schema
    assert "vol.Required(QUICK_SETUP_AREA_KEY)" in schema
    assert "default=15.0" not in schema
    assert "CONF_ROOM_CONTACTS" in schema

def test_quick_success_uses_two_explicit_actions_not_boolean_toggle():
    success=block("async def async_step_quick_success","async def async_step_quick_add_room")
    assert "async_show_menu" in success
    assert 'menu_options=["quick_add_room", "quick_finish"]' in success
    assert "vol.Required" not in success
    assert '"area"' in success and '"height"' in success and '"volume"' in success

def test_precise_setup_stays_precise_for_additional_rooms():
    more=block("async def async_step_more_rooms","async_get_supported_subentry_types")
    assert 'getattr(self, "_setup_mode", "exact") == "quick"' in more
    assert "return await self.async_step_quick_room()" in more
    assert "return await self.async_step_room()" in more
    room=block("async def async_step_room","async def async_step_room_orientations")
    assert "_room_section_schema(" in room

def test_dashboard_category_ownership_is_not_duplicated():
    groups=CARD[CARD.index("const groups={", CARD.index("_settingsGroupMenu")):CARD.index("const titles=",CARD.index("_settingsGroupMenu"))]
    # Each detailed route belongs to one conceptual category only.
    assert groups.count('["cross"') == 1
    assert groups.count('["profile"') == 1
    assert groups.count('["air"') == 1
    assert groups.count('["rooms"') == 1

def test_support_is_separate_from_settings_home():
    home=CARD[CARD.index("_settingsHome()"):CARD.index("_settingsGroupMenu")]
    assert "Diagnosedaten" not in home and "Diagnostic data" not in home
    assert 'id="support"' in CARD and "_supportPanel(st)" in CARD

def test_german_and_english_expose_same_new_flow_keys():
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    assert set(de["config"]["step"])==set(en["config"]["step"])
    for key in ("user","quick_start","quick_room","quick_success"):
        assert key in de["config"]["step"] and key in en["config"]["step"]
