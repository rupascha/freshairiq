from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
FLOW=(ROOT/"custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
CARD=(ROOT/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

CANONICAL_DE=[
"Zuhause einrichten","Bewohner & Anwesenheit","Räume","Lüftungsstrategie",
"Komfort & Gesundheit","Benachrichtigungen","Lernen & Auswertung","Energie & Kosten","Wartung"
]
CANONICAL_EN=[
"Set up home","Residents & presence","Rooms","Ventilation strategy",
"Comfort & health","Notifications","Learning & analytics","Energy & costs","Maintenance"
]

def test_quick_setup_has_visible_success_before_entry_creation():
    quick=FLOW[FLOW.index("async def async_step_quick_room"):FLOW.index("async def async_step_quick_success")]
    assert "async_create_entry" not in quick
    assert "async_step_quick_success" in quick
    success=FLOW[FLOW.index("async def async_step_quick_success"):FLOW.index("async def async_step_more_rooms")]
    assert '"area"' in success and '"height"' in success and '"volume"' in success
    assert "QUICK_SETUP_HEIGHT_M" in success

def test_quick_setup_can_add_multiple_rooms_without_entering_expert_room_form():
    success=FLOW[FLOW.index("async def async_step_quick_success"):FLOW.index("async def async_step_quick_finish")]
    assert 'menu_options=["quick_add_room", "quick_finish"]' in success
    add=FLOW[FLOW.index("async def async_step_quick_add_room"):FLOW.index("async def async_step_quick_finish")]
    assert "async_step_quick_room()" in add
    assert "async_step_room()" not in add

def test_native_and_dashboard_share_canonical_top_level_information_architecture():
    for lang,names in (("de",CANONICAL_DE),("en",CANONICAL_EN)):
        d=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text(encoding="utf-8"))
        init=json.dumps(d["options"]["step"]["init"],ensure_ascii=False)
        for name in names: assert name in init
    home=CARD[CARD.index("_settingsHome()"):CARD.index("_settingsGroupMenu(name)")]
    for name in CANONICAL_DE+CANONICAL_EN: assert name in home

def test_support_remains_outside_settings_information_architecture():
    home=CARD[CARD.index("_settingsHome()"):CARD.index("_settingsGroupMenu(name)")]
    assert "Diagnosedaten" not in home and "Diagnostic data" not in home
    assert 'id="support"' in CARD and "_supportPanel(st)" in CARD

def test_quick_success_transparently_explains_assumed_240m_and_later_editing():
    for lang in ("de","en"):
        d=json.loads((ROOT/f"custom_components/freshairiq/translations/{lang}.json").read_text(encoding="utf-8"))
        q=json.dumps(d["config"]["step"]["quick_success"],ensure_ascii=False)
        assert "{height}" in q and "{volume}" in q and "{area}" in q
        assert ("Schätzung" in q and "Einstellungen" in q) if lang=="de" else ("estimate" in q and "Settings" in q)
