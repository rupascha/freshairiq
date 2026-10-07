from pathlib import Path


def test_room_goal_cards_are_forced_to_one_three_column_row():
    js = Path("custom_components/freshairiq/frontend/freshairiq-card.js").read_text()
    assert ".goal-tracker{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in js
    assert ".goal-pill b{display:none}" in js


def test_options_room_wizard_has_back_contract_without_leaking_to_other_flows():
    src = Path("custom_components/freshairiq/config_flow.py").read_text()
    assert "_goal_priority_schema(room, include_back=True)" in src
    assert "_schema_with_wizard_back(_single_contact_reference_schema(room, contact))" in src
    assert 'if bool(user_input.get("wizard_back")):' in src
    assert "return await self.async_step_edit_room()" in src


def test_idle_blocked_room_is_not_presented_as_room_specific_do_not_ventilate():
    src = Path("custom_components/freshairiq/recommendation.py").read_text()
    block = src[src.index("if blocked_problem_rooms:"):src.index("# Night forecast")]
    assert 'selected=[]' in block
    assert '"Aktuell keine Lüftungsaktion"' in block
