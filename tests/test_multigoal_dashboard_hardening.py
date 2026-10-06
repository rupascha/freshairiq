from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def test_dashboard_contact_reference_pickers_are_searchable_and_filtered():
    assert 'searchableEntity(`contact-ref-temp-' in CARD
    assert 'searchableEntity(`contact-ref-humidity-' in CARD
    assert 'searchableCovers(`contact-cover-' in CARD
    assert '"temperature")' in CARD
    assert '"humidity")' in CARD
    assert 'Search entities …' in CARD


def test_devices_services_contact_reference_selectors_use_device_classes():
    block = FLOW[FLOW.index('def _single_contact_reference_schema'):FLOW.index('def _apply_single_contact_reference')]
    assert 'device_class="temperature"' in block
    assert 'device_class="humidity"' in block


def test_new_and_edited_rooms_pass_through_dynamic_goal_priority_step():
    assert FLOW.count('return await self.async_step_room_goals()') >= 2
    block = FLOW[FLOW.index('async def async_step_room_goals'):FLOW.index('async def async_step_edit_room_select')]
    assert '_available_room_goals(room)' in block
    assert 'if len(available) <= 1' in block
    assert '_goal_priority_errors' in block
    assert '_ranked_goal_priorities' in block


def test_main_decision_renders_canonical_goal_overview_without_recomputing_action():
    assert '_decisionGoalOverview(rooms)' in CARD
    block = CARD[CARD.index('_decisionGoalOverview(rooms)'):CARD.index('_recommendationRows(rooms)')]
    assert 'r.goal_state' in block
    assert 'gs.hard_close' in block
    assert 'Treiber' in block and 'Driver' in block
    assert 'VENTILATION GOALS' in block
    assert 'build_recommendation' not in block
