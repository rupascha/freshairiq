from pathlib import Path
CARD=(Path(__file__).resolve().parents[1]/"custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")

def test_visible_rooms_scope_itself_opens_room_overview():
    assert '["RÄUME","ROOMS"].includes(freshyScope)' in CARD
    assert 'data-info="rooms" role="button"' in CARD
    assert 'if (this._info === "rooms")' in CARD

def test_all_rooms_entry_points_share_existing_navigation_contract():
    assert 'id="rooms"' in CARD
    assert '<div class="ai-all-good clickable" data-info="rooms">' in CARD
    assert 'querySelectorAll("[data-info]")' in CARD
    assert ':not([data-info="rooms"])' not in CARD

def test_house_goal_header_keeps_count_and_has_duration_fallback():
    # 0.26.2.14: the count is written out ("0 von 2 Räumen erreicht") instead of "0/2".
    assert 'session_recommended_duration_min ?? r.recommended_duration_min' in CARD
    assert '${a.reached} von ${a.total} Räumen' in CARD
    assert '${a.reached}/${a.total}' not in CARD
    assert 'mdi:timer-sand' in CARD
    assert 'Math.max(1, Math.round(m))} min' in CARD

def test_compact_room_rows_have_a_complete_defined_border():
    # 0.26.2.14: removing only the top border made the rounded rows look clipped,
    # and the undefined --room-detail colour turned the remaining border white.
    assert 'decision-room-disclosure{border-top:0!important' not in CARD
    assert '.decision-goal-overview .decision-goal-room,.decision-goal-overview .decision-goal-room.decision-room-disclosure{--room-detail:#63d2f7;margin:0;border:0;border-top:1px solid rgba(255,255,255,.06);border-radius:0' in CARD

def test_room_goals_are_labelled_in_words_with_written_priority():
    start=CARD.index("_decisionGoalOverview(rooms")
    end=CARD.index("_infoPanel(", start)
    block=CARD[start:end]
    assert '${de ? "Priorität" : "Priority"}:' in block
    assert '${de?"Prio":"Priority"}:' not in block
    assert 'class="goal-kind"' in block
    assert 'aria-label="${esc(title)}"' in block
    assert 'class="goal-room-status ${statusClass}"' in block
