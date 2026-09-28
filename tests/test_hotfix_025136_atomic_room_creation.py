from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _native_add_finalize_block() -> str:
    start = FLOW.index("async def async_step_add_references")
    end = FLOW.index("def _persist_room_update", start)
    return FLOW[start:end]


def test_native_create_does_not_publish_parent_room_before_create_entry():
    block = _native_add_finalize_block()
    create_pos = block.index("return self.async_create_entry(")
    before = block[:create_pos]
    # The only parent update belongs to the post-commit coroutine, after its
    # explicit yield + committed-subentry guard.
    update_pos = before.index("self.hass.config_entries.async_update_entry(entry, data=data)")
    guard_pos = before.index("if committed is None:")
    yield_pos = before.index("await asyncio.sleep(0)")
    assert yield_pos < guard_pos < update_pos
    assert "self.hass.loop.call_soon(" not in block


def test_parent_sync_requires_committed_matching_room_subentry():
    block = _native_add_finalize_block()
    assert 'subentry.subentry_type == "room"' in block
    assert "subentry.unique_id == unique_id" in block
    assert "if committed is None:" in block
    assert "return" in block[block.index("if committed is None:"):block.index("rooms = [dict(existing)")]


def test_successful_post_commit_sync_updates_parent_then_reloads():
    block = _native_add_finalize_block()
    update = block.index("self.hass.config_entries.async_update_entry(entry, data=data)")
    reload_ = block.index("self.hass.config_entries.async_schedule_reload(entry.entry_id)")
    assert update < reload_
    assert "self.hass.async_create_task(_commit_parent_after_subentry())" in block
    assert 'unique_id=unique_id' in block


def test_room_creation_hotfix_version_025136():
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.36.md").is_file()
    assert 'VERSION = "0.25.1.36"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
