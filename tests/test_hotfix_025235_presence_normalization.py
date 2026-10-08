from custom_components.freshairiq.presence import normalize_presence_state, presence_diagnostics, resolve_occupancy
from custom_components.freshairiq.personal_context import build_resident_context

class State:
    def __init__(self, state):
        self.state = state
        self.attributes = {}

class States(dict):
    def get(self, key, default=None): return super().get(key, default)

def test_person_zone_is_away_but_custom_device_tracker_is_unknown():
    assert normalize_presence_state("person.a", State("work")) == "away"
    assert normalize_presence_state("device_tracker.watch", State("work")) == "unknown"
    assert normalize_presence_state("device_tracker.watch", State("not_home")) == "away"
    assert normalize_presence_state("device_tracker.watch", State("home")) == "home"

def test_occupancy_and_personal_context_share_normalization():
    states = States({"device_tracker.watch": State("private_ble_custom")})
    opts = {"adult_occupants": 1, "adult_resident_names": "A", "adult_presence_entities": ["device_tracker.watch"]}
    occ = resolve_occupancy(opts, states.get)
    ctx = build_resident_context(opts, states)
    assert occ["unknown_adults"] == 1 and occ["away_adults"] == 0
    assert ctx["residents"][0]["presence"] == "unknown"

def test_presence_diagnostics_is_aggregate_and_privacy_safe():
    states = {"person.a": State("office"), "device_tracker.watch": State("private_ble_custom"), "device_tracker.phone": State("home")}
    opts = {"adult_presence_entities": ["person.a", "device_tracker.watch", "device_tracker.phone"], "child_presence_entities": []}
    d = presence_diagnostics(opts, states.get)
    assert d["normalized"] == {"home": 1, "away": 1, "unknown": 1}
    assert d["domains"] == {"person": 1, "device_tracker": 2}
    assert d["raw_state_classes"]["custom"] == 2
    blob = str(d)
    assert "person.a" not in blob and "private_ble_custom" not in blob

def test_presence_normalization_unknown_missing_and_legacy_home_edges():
    assert normalize_presence_state("device_tracker.x", None) == "unknown"
    assert normalize_presence_state("device_tracker.x", State("unavailable")) == "unknown"
    from custom_components.freshairiq import presence
    assert presence._state_kind(State("home")) == "home"
    d = presence_diagnostics({"adult_presence_entities": ["device_tracker.missing"]}, lambda _eid: None)
    assert d["raw_state_classes"]["missing"] == 1
