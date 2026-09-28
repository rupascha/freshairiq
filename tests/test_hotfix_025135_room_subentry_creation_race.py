from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _native_add_finalize_block() -> str:
    start = FLOW.index("async def async_step_add_references")
    end = FLOW.index("def _persist_room_update", start)
    return FLOW[start:end]


def test_native_room_create_does_not_reload_parent_synchronously_before_create_entry():
    block = _native_add_finalize_block()
    # v0.25.1.36 strengthens this historical contract: the parent mutation and
    # reload now live behind a verified post-subentry-commit guard. There must
    # still be no direct/synchronous reload in the CREATE_ENTRY return path.
    create_pos = block.index("return self.async_create_entry(")
    direct_path = block[block.index("self.hass.async_create_task(_commit_parent_after_subentry())"):create_pos]
    assert "async_schedule_reload(entry.entry_id)" not in direct_path
    assert "await self.hass.config_entries.async_reload" not in block


def test_native_room_create_keeps_parent_and_subentry_contract():
    block = _native_add_finalize_block()
    assert "rooms.append(room_to_commit)" in block
    assert "data[CONF_ROOMS] = rooms" in block
    assert "async_update_entry(entry, data=data)" in block
    assert 'unique_id = f"room:{room_to_commit[\'key\']}"' in block
    assert "data=room_to_commit" in block


def test_deferred_reload_is_scheduled_before_return_without_awaiting_or_immediate_reload():
    block = _native_add_finalize_block()
    assert "await self.hass.config_entries.async_reload" not in block
    assert "self.hass.loop.call_soon(" not in block
    assert "await asyncio.sleep(0)" in block
    assert "if committed is None:" in block
    assert block.index("self.hass.async_create_task(_commit_parent_after_subentry())") < block.index("return self.async_create_entry(")
