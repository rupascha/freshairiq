from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _native_add_finalize_block() -> str:
    start = FLOW.index("async def async_step_add_references")
    end = FLOW.index("def _persist_room_update", start)
    return FLOW[start:end]


def test_native_room_create_does_not_reload_parent_synchronously_before_create_entry():
    block = _native_add_finalize_block()
    update_pos = block.index("async_update_entry(entry, data=data)")
    create_pos = block.index("return self.async_create_entry(")
    between = block[update_pos:create_pos]
    assert "async_schedule_reload(entry.entry_id)" not in between
    assert "self.hass.loop.call_soon(" in between
    assert "self.hass.config_entries.async_schedule_reload, entry.entry_id" in between


def test_native_room_create_keeps_parent_and_subentry_contract():
    block = _native_add_finalize_block()
    assert "rooms.append(room)" in block
    assert "data[CONF_ROOMS] = rooms" in block
    assert "async_update_entry(entry, data=data)" in block
    assert 'unique_id=f"room:{room[\'key\']}"' in block
    assert "data=room" in block


def test_deferred_reload_is_scheduled_before_return_without_awaiting_or_immediate_reload():
    block = _native_add_finalize_block()
    assert "await self.hass.config_entries.async_reload" not in block
    assert "self.hass.loop.call_soon(" in block
    assert block.index("self.hass.loop.call_soon(") < block.index("return self.async_create_entry(")
