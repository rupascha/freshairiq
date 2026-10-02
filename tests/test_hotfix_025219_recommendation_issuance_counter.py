from datetime import datetime, timedelta

from custom_components.freshairiq.intelligence import sync_active_recommendation, mark_recommendation_followed


def _rec(kind="ventilate", rooms=None):
    return {"kind": kind, "room_keys": rooms if rooms is not None else ["living"], "duration_min": 10}


def test_opportunity_counts_immediately_and_refresh_does_not_duplicate():
    now = datetime(2026, 10, 2, 12, 0)
    store = {"rooms": {"living": {}}}
    assert sync_active_recommendation(store, _rec(), now) is True
    room = store["rooms"]["living"]
    assert room["recommendation_opportunities"] == 1
    assert room["recommendation_followed"] == 0
    assert room["recommendation_missed"] == 0
    assert sync_active_recommendation(store, _rec(), now + timedelta(minutes=1)) is False
    assert room["recommendation_opportunities"] == 1


def test_finalize_only_classifies_followed_or_missed():
    now = datetime(2026, 10, 2, 12, 0)
    store = {"rooms": {"living": {}}}
    sync_active_recommendation(store, _rec(), now)
    room = store["rooms"]["living"]
    assert mark_recommendation_followed(store, room, "living", now + timedelta(minutes=2))
    sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, now + timedelta(minutes=3))
    assert room["recommendation_opportunities"] == 1
    assert room["recommendation_followed"] == 1
    assert room["recommendation_missed"] == 0
    assert room["recommendation_followed"] + room["recommendation_missed"] <= room["recommendation_opportunities"]


def test_unfollowed_episode_is_missed_without_second_opportunity():
    now = datetime(2026, 10, 2, 12, 0)
    store = {"rooms": {"living": {}}}
    sync_active_recommendation(store, _rec(), now)
    room = store["rooms"]["living"]
    sync_active_recommendation(store, {"kind": "okay", "room_keys": []}, now + timedelta(minutes=3))
    assert (room["recommendation_opportunities"], room["recommendation_followed"], room["recommendation_missed"]) == (1, 0, 1)


def test_replacement_counts_one_new_episode_and_finalizes_previous():
    now = datetime(2026, 10, 2, 12, 0)
    store = {"rooms": {"living": {}, "bed": {}}}
    sync_active_recommendation(store, _rec(rooms=["living"]), now)
    sync_active_recommendation(store, _rec(rooms=["bed"]), now + timedelta(minutes=3))
    living, bed = store["rooms"]["living"], store["rooms"]["bed"]
    assert (living["recommendation_opportunities"], living["recommendation_missed"]) == (1, 1)
    assert (bed["recommendation_opportunities"], bed["recommendation_missed"]) == (1, 0)


def test_issuance_skips_corrupt_room_without_blocking_valid_room():
    now = datetime(2026, 10, 2, 12, 0)
    store = {"rooms": {"broken": "invalid", "living": {}}}
    assert sync_active_recommendation(store, _rec(rooms=["broken", "living"]), now) is True
    assert store["rooms"]["broken"] == "invalid"
    assert store["rooms"]["living"]["recommendation_opportunities"] == 1
