from custom_components.freshairiq.presence import resolve_occupancy


class State:
    def __init__(self, state): self.state = state


def test_presence_tracks_adults_and_untracked_children_follow_household():
    states = {"person.a": State("home"), "person.b": State("not_home")}
    opts = {
        "adult_occupants": 2, "child_occupants": 2,
        "adult_presence_entities": ["person.a", "person.b"],
        "child_presence_entities": [],
        "untracked_follow_household": True,
        "guest_adults": 0, "guest_children": 0,
    }
    r = resolve_occupancy(opts, states.get)
    assert r["expected_adults"] == 1
    assert r["expected_children"] == 2
    assert r["expected_total"] == 3


def test_untracked_children_follow_all_tracked_residents_away():
    states = {"person.a": State("not_home"), "person.b": State("not_home")}
    opts = {
        "adult_occupants": 2, "child_occupants": 2,
        "adult_presence_entities": ["person.a", "person.b"],
        "child_presence_entities": [],
        "untracked_follow_household": True,
    }
    r = resolve_occupancy(opts, states.get)
    assert r["expected_total"] == 0


def test_guest_reactivates_household_and_is_counted():
    states = {"person.a": State("not_home"), "person.b": State("not_home")}
    opts = {
        "adult_occupants": 2, "child_occupants": 2,
        "adult_presence_entities": ["person.a", "person.b"],
        "child_presence_entities": [],
        "untracked_follow_household": True,
        "guest_adults": 1, "guest_children": 1,
    }
    r = resolve_occupancy(opts, states.get)
    assert r["expected_adults"] == 1
    assert r["expected_children"] == 3
    assert r["expected_total"] == 4
