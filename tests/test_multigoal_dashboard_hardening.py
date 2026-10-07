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
    assert '_decisionGoalOverview(rooms, passiveOpenMonitor=false)' in CARD
    block = CARD[CARD.index('_decisionGoalOverview(rooms, passiveOpenMonitor=false)'):CARD.index('_recommendationRows(rooms)')]
    assert 'r.goal_state' in block
    assert 'gs.hard_close' in block
    assert 'Prio' in block and 'Priority' in block
    assert 'Treiber' not in block
    assert 'Räume & Ziele anzeigen' in block and 'Show rooms & goals' in block
    assert 'mdi:water-outline' in block
    assert 'mdi:thermometer' in block
    assert 'mdi:molecule-co2' in block
    assert 'mdi:timer-sand' in block
    assert 'nicht erreichbar' in block and 'unreachable' in block
    assert 'Schutzregel hat Vorrang vor noch offenen Zielen.' not in block
    assert 'build_recommendation' not in block


def test_house_goal_dashboard_is_progressively_disclosed_and_icon_first():
    main = CARD[CARD.index('return `<section class="decision-card ai-card"'):CARD.index('_recommendationRows(rooms)')]
    assert main.count('_decisionGoalOverview(selectedRoomObjs, passiveOpenMonitor)') == 1
    assert 'selectedRoomObjs.map(r =>' not in main
    block = CARD[CARD.index('_decisionGoalOverview(rooms, passiveOpenMonitor=false)'):CARD.index('_recommendationRows(rooms)')]
    assert 'decision-house-goals' in block
    assert 'Math.max(...a.eta)' in block
    assert '${a.reached}/${a.total}' in block
    assert '<b>${esc(labels[g.id]||g.id)}</b>' not in block
    assert 'goalNames[g.id]' not in block.split('return `<span class="decision-goal-icon', 1)[1].split('</span>`;', 1)[0]
