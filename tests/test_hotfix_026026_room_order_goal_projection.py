from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'custom_components/freshairiq'
CARD=(COMP/'frontend/freshairiq-card.js').read_text()
API=(COMP/'feedback_api.py').read_text()
FLOW=(COMP/'config_flow.py').read_text()

# test_dashboard_room_order_remains_immediate_tile_controls: retired — dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services).

def test_dashboard_goal_order_is_immediate_tile_controls_and_server_validated():
    assert 'settings-goal-order-list' in CARD
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).
    # removed: dashboard-side check (dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services)).

def test_native_priority_flow_persists_once_without_reload_and_returns_to_room_choice():
    block=FLOW[FLOW.index('async def async_step_recommendation_priority_order'):FLOW.index('async def async_step_cross_ventilation')]
    assert '_persist_working_state(reload_entry=False)' in block
    assert 'return await self.async_step_recommendation_priorities()' in block
    assert 'wizard_back' in block

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
