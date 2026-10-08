from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")


def test_room_sort_is_all_at_once_and_has_back_path():
    block = FLOW[FLOW.index("async def async_step_sort_rooms"):FLOW.index("async def async_step_contact_orientations_room")]
    assert 'room_position_{idx}' in block
    assert '"wizard_back"' in block
    assert "return await self.async_step_rooms()" in block
    assert "room_to_move" not in block
    assert "move_direction" not in block
    assert "_persist_working_state(reload_entry=False)" in block


def test_goal_sort_is_all_at_once_validated_and_has_back_path():
    helper = FLOW[FLOW.index("def _goal_priority_schema"):FLOW.index("# Legacy room-level reference keys")]
    assert 'goal_priority_{idx}' in helper
    assert "duplicate_goal_order" in helper
    assert "invalid_goal_order" in helper
    assert "goal_to_move" not in helper
    assert "move_direction" not in helper
    block = FLOW[FLOW.index("async def async_step_recommendation_priority_order"):FLOW.index("async def async_step_cross_ventilation")]
    assert '"wizard_back"' in block
    assert "_persist_working_state(reload_entry=False)" in block


def test_room_goal_wizard_exposes_the_back_control_it_handles():
    assert "_goal_priority_schema(room, include_back=True)" in FLOW
    assert 'user_input.get("wizard_back")' in FLOW


def test_de_en_ordering_copy_is_complete():
    for language in ("de", "en"):
        data = json.loads((COMP / "translations" / f"{language}.json").read_text(encoding="utf-8"))
        steps = data["options"]["step"]
        assert "wizard_back" in steps["sort_rooms"]["data"]
        assert all(f"room_position_{i}" in steps["sort_rooms"]["data"] for i in range(1, 13))
        assert "wizard_back" in steps["recommendation_priority_order"]["data"]
        assert all(f"goal_priority_{i}" in steps["recommendation_priority_order"]["data"] for i in range(1, 4))
        assert "invalid_room_order" in data["options"]["error"]
        assert "duplicate_goal_order" in data["options"]["error"]
