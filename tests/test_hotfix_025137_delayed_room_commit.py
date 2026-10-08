import asyncio
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _native_add_finalize_block() -> str:
    start = FLOW.index("async def async_step_add_references")
    end = FLOW.index("def _persist_room_update", start)
    return FLOW[start:end]


def test_delayed_commit_wait_is_bounded_and_checks_each_turn():
    block = _native_add_finalize_block()
    assert "for _attempt in range(20):" in block
    assert "await asyncio.sleep(0.05)" in block
    assert "if committed is not None:" in block
    assert "break" in block
    assert block.index("if committed is None:") < block.index("rooms = [dict(existing)")


def test_parent_update_still_requires_real_matching_ha_subentry():
    block = _native_add_finalize_block()
    assert 'subentry.subentry_type == "room"' in block
    assert "subentry.unique_id == unique_id" in block
    assert "self.hass.config_entries.async_update_entry(entry, data=data)" in block
    assert "self.hass.config_entries.async_schedule_reload(entry.entry_id)" in block


def test_delayed_commit_regression_model():
    async def wait_for_commit(entry, unique_id):
        committed = None
        for _attempt in range(20):
            await asyncio.sleep(0.001)
            committed = next(
                (sub for sub in entry.subentries.values() if sub.subentry_type == "room" and sub.unique_id == unique_id),
                None,
            )
            if committed is not None:
                break
        return committed

    async def scenario():
        entry = SimpleNamespace(subentries={})
        waiter = asyncio.create_task(wait_for_commit(entry, "room:kinderzimmer"))
        # Reproduce HA finishing CREATE_ENTRY later than the first scheduler turn.
        await asyncio.sleep(0.003)
        entry.subentries["sub-1"] = SimpleNamespace(subentry_type="room", unique_id="room:kinderzimmer")
        return await waiter

    committed = asyncio.run(scenario())
    assert committed is not None
    assert committed.unique_id == "room:kinderzimmer"


def test_room_creation_hotfix_release_025137_is_retained():
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.37.md").is_file()
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    version = const.split('VERSION = "', 1)[1].split('"', 1)[0]
    assert tuple(map(int, version.split("."))) >= (0, 25, 1, 37)
