from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'custom_components/freshairiq'
CARD=(COMP/'frontend/freshairiq-card.js').read_text()
API=(COMP/'settings_api.py').read_text()
FLOW=(COMP/'config_flow.py').read_text()

def test_dashboard_room_order_remains_immediate_tile_controls():
    assert 'data-room-move="up"' in CARD
    assert 'data-room-move="down"' in CARD
    assert 'action: "reorder_rooms"' in CARD

def test_dashboard_goal_order_is_immediate_tile_controls_and_server_validated():
    assert 'settings-goal-order-list' in CARD
    assert 'data-goal-move="up"' in CARD and 'data-goal-move="down"' in CARD
    assert 'action:"reorder_room_goals"' in CARD
    assert 'elif action == "reorder_room_goals"' in API
    assert 'set(requested) != set(available)' in API

def test_native_priority_flow_does_not_eject_after_each_move():
    block=FLOW[FLOW.index('async def async_step_recommendation_priority_order'):FLOW.index('async def async_step_cross_ventilation')]
    assert 'return await self.async_step_recommendation_priority_order()' in block
    assert 'return await self.async_step_ventilation_settings()' not in block

def test_room_goal_cards_show_directional_ventilation_impacts():
    assert 'forecast_physical_moisture_effect_ml' in CARD
    assert 'forecast_temperature_change_c' in CARD
    assert '−${Math.round(potential)} ml' in CARD
    assert '+${Math.abs(Math.round(effect))} ml' in CARD
    assert '−${Math.round(delta)} ppm' in CARD
    assert 'Ziel erreicht' not in CARD[CARD.index('_goalTracker(r, compact=false)'):CARD.index('_roomCard(r)')]

def test_expanded_room_list_first_row_has_no_clipped_top_border():
    assert '.decision-goal-room-list{margin-top:7px;padding-top:2px;overflow:visible}' in CARD
    assert '.decision-goal-room:first-child{border-top:0}' in CARD
