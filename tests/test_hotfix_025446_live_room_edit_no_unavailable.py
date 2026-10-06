from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = (ROOT / "custom_components/freshairiq/settings_api.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")

def test_dashboard_existing_room_edit_uses_live_runtime_refresh():
    block = SETTINGS[SETTINGS.index('elif action == "upsert_room":'):SETTINGS.index('elif action == "delete_room":')]
    assert "if keep_key:" in block
    assert "await _apply_runtime_update(hass, entry, rebuild_listeners=True)" in block
    assert "else:" in block
    assert "async_schedule_reload(entry.entry_id)" in block

def test_native_room_subentries_are_add_only_not_reconfigurable():
    start = FLOW.index("class FreshAirIQRoomSubentryFlow")
    end = FLOW.index("class FreshAirIQOptionsFlow", start)
    block = FLOW[start:end]
    assert "async def async_step_user" in block
    assert "async def async_step_reconfigure" not in block
    assert "async def _async_step_reconfigure_legacy" in block

def test_native_save_room_uses_live_runtime_refresh():
    start = FLOW.index("async def async_step_save_room")
    end = FLOW.index("class FreshAirIQOptionsFlow", start)
    block = FLOW[start:end]
    assert "_schedule_room_runtime_update()" in block
    assert "async_schedule_reload" not in block

def test_options_flow_only_room_topology_change_is_structural():
    assert 'structural_change = old_room_keys != new_room_keys' in FLOW
