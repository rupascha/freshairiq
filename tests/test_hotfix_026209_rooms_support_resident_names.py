from pathlib import Path
import sys, types
if "homeassistant" not in sys.modules:
    ha=types.ModuleType("homeassistant"); core=types.ModuleType("homeassistant.core")
    class HomeAssistant: pass
    core.HomeAssistant=HomeAssistant; ha.core=core
    sys.modules["homeassistant"]=ha; sys.modules["homeassistant.core"]=core
from custom_components.freshairiq.notifications import _resident_profiles

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')

def test_all_rooms_triggers_use_one_supported_room_overlay_path():
    assert '<div class="ai-all-good clickable" data-info="rooms">' in CARD
    assert 'querySelectorAll("[data-info]")' in CARD
    assert '[data-info]:not([data-info="rooms"])' not in CARD
    assert 'if (this._info === "rooms")' in CARD

def test_support_diagnostics_button_has_no_duplicate_send_wording():
    assert '<b>Diagnosedaten</b><span>an Support senden</span>' in CARD
    assert 'An Support senden<span>direkt an Support senden</span>' not in CARD
    assert '<b>Diagnosedatei</b><span>direkt an Support senden</span>' not in CARD

def test_resident_notification_profile_uses_configured_name_as_fallback():
    options = {
        'adult_resident_names': 'Anna, Ben',
        'resident_room_profiles': {
            'adult:0': {'room_keys':['living'], 'notification_targets':['notify.a']},
            'adult:1': {'name':'', 'room_keys':['office'], 'notification_targets':['notify.b']},
        },
    }
    profiles = _resident_profiles(options)
    assert [p['name'] for p in profiles] == ['Anna', 'Ben']

def test_configured_name_wins_and_placeholders_never_address_anyone():
    # 0.26.4.1 (community report): messages started with "Erwachsener 1" although a
    # name was configured. The configured household name is the truth for a slot.
    configured = {'adult_resident_names': 'Anna', 'resident_room_profiles': {'adult:0': {'name': 'Existing', 'notification_targets': ['notify.a']}}}
    assert _resident_profiles(configured)[0]['name'] == 'Anna'
    placeholder = {'adult_resident_names': 'Anna, Ben', 'resident_room_profiles': {'adult:1': {'name': 'Erwachsener 2', 'notification_targets': ['notify.b']}}}
    assert _resident_profiles(placeholder)[0]['name'] == 'Ben'
    unnamed = {'resident_room_profiles': {'adult:0': {'name': 'Erwachsener 1', 'notification_targets': ['notify.a']}}}
    assert _resident_profiles(unnamed)[0]['name'] == ''
    reordered = {'adult_resident_names': 'Ben, Anna', 'resident_room_profiles': {'adult:0': {'name': 'Anna', 'notification_targets': ['notify.a']}}}
    assert _resident_profiles(reordered)[0]['name'] == 'Anna'
    legacy = {'resident_room_profiles': {'adult:0': {'name': 'Paul', 'notification_targets': ['notify.p']}}}
    assert _resident_profiles(legacy)[0]['name'] == 'Paul'
