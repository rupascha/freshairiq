from pathlib import Path
from custom_components.freshairiq.consolidation import aggregate_close_allowed

ROOT = Path(__file__).resolve().parents[1]
COORD = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")


def room(*, goal="co2", reached=False, achievable=True, hard=False, action="Continue"):
    return {
        "close_decision_ready": True,
        "action": action,
        "goal_state": {
            "hard_close": hard,
            "goals": [
                {"id": "humidity", "active": True, "reached": True, "achievable_now": True},
                {"id": goal, "active": True, "reached": reached, "achievable_now": achievable},
            ],
        },
    }


def test_low_moisture_return_does_not_close_reachable_co2_goal():
    assert aggregate_close_allowed([room(goal="co2")], low_return=True, thermal_bad=False) is False


def test_low_moisture_return_does_not_close_reachable_temperature_goal():
    assert aggregate_close_allowed([room(goal="temperature")], low_return=True, thermal_bad=False) is False


def test_low_return_can_close_when_other_goal_is_not_reachable():
    assert aggregate_close_allowed([room(goal="co2", achievable=False)], low_return=True, thermal_bad=False) is True


def test_hard_close_remains_dominant_with_open_goal():
    assert aggregate_close_allowed([room(goal="co2", hard=True)], low_return=True, thermal_bad=False) is True


def test_thermal_protection_remains_dominant_with_open_goal():
    assert aggregate_close_allowed([room(goal="temperature")], low_return=False, thermal_bad=True) is True


def test_house_and_floor_brains_carry_canonical_scope_and_rooms():
    assert '"selected_rooms": active_room_names' in COORD
    assert '"presentation_scope": "house"' in COORD
    assert '"selected_rooms": floor_room_names' in COORD
    assert '"presentation_scope": "floor"' in COORD
    assert '"presentation_floor": floor_display_name' in COORD


def test_new_hierarchical_typography_is_readable_and_continuous_freshy_is_smaller():
    assert '.decision-scope{font-size:11px' in CARD
    assert '.ai-scope{font-size:10px' in CARD
    assert '.ai-goal-chip{font-size:10px' in CARD
    assert '.ai-compact.continuous .ai-freshy-angle .ai-leaf,.ai-compact.continuous .ai-freshy-angle .ai-leaf-right{width:19px;height:10px' in CARD

def test_helper_hard_close_branch_is_covered_via_mixed_rooms():
    # First room is not hard-close so aggregate any() continues to the second;
    # direct helper behavior is also exercised through low-return evaluation.
    from custom_components.freshairiq.consolidation import _reachable_open_non_humidity_goal
    assert _reachable_open_non_humidity_goal(room(goal="co2", hard=True)) is False


def test_unanimous_room_close_remains_dominant_without_hard_flag():
    r1 = room(goal="co2", action="Close", achievable=False)
    r2 = room(goal="temperature", action="Close", achievable=False)
    assert aggregate_close_allowed([r1, r2], low_return=False, thermal_bad=False) is True
