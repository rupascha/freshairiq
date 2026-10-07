from custom_components.freshairiq.language_confidence import adapt_language_confidence, room_notification_message


def _room(samples=15):
    return {"key":"office","name":"Arbeitszimmer","learning_samples":samples,"forecast_observation_samples":4,"outcome_feedback_samples":3,"strategy_samples":2,"behaviour_recommendation_opportunities":2,"forecast_confidence":72,"measurement_frame_quality":"excellent"}


def _rec(kind="wait"):
    title={"wait":"Noch warten","ventilate":"Jetzt lüften","continue":"Lüftung läuft","close":"Jetzt schließen"}.get(kind,"Okay")
    return {"kind":kind,"status":"waiting" if kind=="wait" else kind,"room_keys":["office"],"title":title,"summary":"Basis.","decision_brain":{"headline":title,"summary":"Basis.","why":[],"impact":{"confidence":75}}}


def test_same_decision_episode_keeps_wording_stable():
    store={}
    a=adapt_language_confidence(_rec("wait"),{"office":_room()},store)
    b=adapt_language_confidence(_rec("wait"),{"office":_room()},store)
    assert a["title"] == b["title"]
    assert a["summary"] == b["summary"]


def test_returning_decision_rotates_without_changing_action():
    store={}
    first=adapt_language_confidence(_rec("wait"),{"office":_room()},store)
    adapt_language_confidence(_rec("ventilate"),{"office":_room()},store)
    second=adapt_language_confidence(_rec("wait"),{"office":_room()},store)
    assert first["kind"] == second["kind"] == "wait"
    assert first["room_keys"] == second["room_keys"] == ["office"]
    assert first["title"] != second["title"]
    assert first["summary"] != second["summary"]


def test_low_maturity_wording_is_cautious_and_exposed():
    out=adapt_language_confidence(_rec("wait"),{"office":_room(15)},{})
    assert out["language_confidence"]["maturity_band"] in {"grundmodell","beobachtet"}
    assert out["language_confidence"]["narrative_variation"] is True
    assert "noch" in out["summary"].lower() or "vorsichtig" in out["summary"].lower() or "mess" in out["summary"].lower()


def test_room_notification_variants_are_stable_and_rotate_after_other_episode():
    store={}; room=_room()
    a=room_notification_message("ventilate",room,store)
    assert a == room_notification_message("ventilate",room,store)
    # A different room notification event does not alter the canonical event text.
    room_notification_message("close",room,store)
    assert a == room_notification_message("ventilate",room,store)


def test_narrative_never_changes_canonical_fields():
    store={}; rec=_rec("close"); rec.update({"duration_min":7,"selected_option_id":"now"})
    out=adapt_language_confidence(rec,{"office":_room(80)},store)
    assert out["kind"] == "close"
    assert out["duration_min"] == 7
    assert out["selected_option_id"] == "now"
    assert out["room_keys"] == ["office"]


def test_variant_state_hardening_and_bounded_history():
    from custom_components.freshairiq import language_confidence as lc
    assert lc._variant_index({}, "x", "s", 1) == 0
    store={"narrative_variants":"corrupt"}
    assert lc._variant_index(store,"x","s",2) == 0
    assert isinstance(store["narrative_variants"],dict)
    state=store["narrative_variants"]
    for i in range(45):
        lc._variant_index(store,f"room_notification:test:{i}",f"s{i}",2)
    assert len(state) <= 40
