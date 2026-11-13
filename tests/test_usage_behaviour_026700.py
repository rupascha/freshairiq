"""0.26.7.0 "Nutzungsverhalten & Empfehlungen" (owner order point 6), built into the existing episode tracking.

Metric check first: the historical follow rate counts every episode – also while everybody was away (nobody could
act) and while FreshAirIQ's own fan automation carried it out. Those are now kept apart as "without a chance to act";
the historical counters keep their definition (published values are not rewritten). The section only observes:
it changes no recommendation, no notification and never a protection, CO₂ or critical humidity warning.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.freshairiq.intelligence import ensure_behaviour_defaults, mark_recommendation_followed, sync_active_recommendation
from custom_components.freshairiq.learning_components import build_learning_components_status

T0 = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)


def _store():
    room: dict = {}
    ensure_behaviour_defaults(room)
    return {"rooms": {"bad": room}}


def _episode(store, *, start, context, follow=False, later_context=None):
    sync_active_recommendation(store, {"kind": "ventilate", "room_keys": ["bad"], "duration_min": 10}, start, context)
    if later_context is not None:
        sync_active_recommendation(store, {"kind": "ventilate", "room_keys": ["bad"], "duration_min": 10}, start + timedelta(minutes=5), later_context)
    if follow:
        mark_recommendation_followed(store, store["rooms"]["bad"], "bad", start + timedelta(minutes=7))
    sync_active_recommendation(store, {"kind": "none", "room_keys": []}, start + timedelta(minutes=30), context)


def test_unactionable_episodes_are_kept_apart_and_old_counters_keep_their_definition():
    store = _store()
    _episode(store, start=T0, context={"away": True})                                       # nobody home
    _episode(store, start=T0 + timedelta(hours=1), context={"automatic": True})             # FreshAirIQ's fan did it
    _episode(store, start=T0 + timedelta(hours=2), context={}, follow=True)                 # followed
    _episode(store, start=T0 + timedelta(hours=3), context={})                              # ignored
    room = store["rooms"]["bad"]
    assert (room["recommendation_opportunities"], room["recommendation_followed"], room["recommendation_missed"]) == (4, 1, 3)
    assert room["recommendation_follow_rate"] == 25.0                                       # historical definition
    assert (room["recommendation_actionable"], room["recommendation_actionable_followed"], room["recommendation_unactionable"]) == (2, 1, 2)
    assert room["recommendation_actionable_follow_rate"] == 50.0
    assert room["recommendation_ignored_streak"] == 1


def test_coming_home_during_an_episode_makes_it_actionable():
    store = _store()
    _episode(store, start=T0, context={"away": True}, later_context={})
    assert store["rooms"]["bad"]["recommendation_actionable"] == 1 and store["rooms"]["bad"]["recommendation_unactionable"] == 0


def test_episodes_from_before_the_update_are_not_reclassified():
    store = _store()
    sync_active_recommendation(store, {"kind": "ventilate", "room_keys": ["bad"]}, T0, None)
    store["iq_active_advice"].pop("actionable")                                             # stored by an older version
    sync_active_recommendation(store, {"kind": "none", "room_keys": []}, T0 + timedelta(minutes=30))
    room = store["rooms"]["bad"]
    assert room["recommendation_missed"] == 1 and room["recommendation_actionable"] == 0 and room["recommendation_unactionable"] == 0


def test_section_is_observation_only_and_explains_itself():
    rows = [{"key": "bad", "data_quality": "ok", "behaviour_actionable": 6, "behaviour_actionable_followed": 3,
             "behaviour_unactionable": 4, "behaviour_ignored_streak": 2}]
    status = build_learning_components_status(rows, {}, forecast_backtest={}, post_close_stabilization={})
    section = {c["key"]: c for c in status["components"]}["usage_behaviour"]
    assert section["label"] == "Nutzungsverhalten & Empfehlungen" and section["observation_only"] is True
    assert "6 Empfehlungen mit Handlungsmöglichkeit · 50 % umgesetzt · 4 ohne Handlungsmöglichkeit" in section["detail"]
    assert "CO₂" in section["description"] and "keine Benachrichtigung" in section["description"]
