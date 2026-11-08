"""0.26.7.0: where an opening leads (contact_sides.py) – pure rules behind the inside-door handling."""
from __future__ import annotations

from custom_components.freshairiq import contact_sides as cs
from custom_components.freshairiq.robustness import prepare_runtime_rooms

W, D, D2 = "binary_sensor.fenster", "binary_sensor.tuer", "binary_sensor.tuer2"


def _room(key="bad", contacts=(W, D), sides=None, connected=None, **extra):
    room = {"key": key, "name": key.title(), "contacts": list(contacts), **extra}
    if sides is not None:
        room["contact_sides"] = sides
    if connected is not None:
        room["contact_connected_rooms"] = connected
    return room


def test_configured_contacts_cover_every_stored_form() -> None:
    assert cs.configured_contacts({"contacts": W}) == [W]
    assert cs.configured_contacts({"contacts": ""}) == []
    assert cs.configured_contacts({"contacts": [W, W, "", D]}) == [W, D]
    assert cs.configured_contacts({"contact": D}) == [D]
    assert cs.configured_contacts({}) == []
    assert cs.configured_contacts({"_all_contacts": [W, D], "contacts": [W]}) == [W, D]


def test_side_and_connected_room_default_to_the_outside_behaviour() -> None:
    room = _room(sides={D: "inside", W: "bogus"}, connected={D: "flur", W: "flur"})
    assert (cs.side(room, W), cs.side(room, D), cs.side(_room(), D)) == ("outside", "inside", "outside")
    assert cs.connected_room(room, D) == "flur" and cs.connected_room(room, W) is None
    assert cs.connected_room(_room(sides={D: "inside"}, connected={D: "bad"}), D) is None        # never the room itself
    assert cs.connected_room(_room(sides={D: "inside"}, connected=["flur"]), D) is None          # malformed mapping
    assert cs.side(_room(sides=["inside"]), D) == "outside"


def test_conflicts_runtime_view_and_inside_contacts() -> None:
    rooms = [_room("bad", sides={D: "inside"}), _room("flur", contacts=(D,)), "kaputt"]
    assert cs.side_conflicts(rooms) == {D: ["bad", "flur"]}
    assert cs.conflicting_side(rooms, "flur", D, "outside") == "Bad"
    assert cs.conflicting_side(rooms, "flur", D, "inside") is None            # the other room says inside as well
    assert cs.conflicting_side([_room("bad", sides={D: "inside"})], "neu", D, "inside") is None
    view = cs.runtime_view(_room(sides={D: "inside"}, contact=D))
    assert view["contacts"] == [W] and view["_inside_contacts"] == [D] and "contact" not in view
    kept = cs.runtime_view(_room(sides={D: "inside"}), conflicts=[D])
    assert kept["contacts"] == [W, D] and kept["_inside_contacts"] == []
    assert cs.inside_contacts(view) == [D] and cs.inside_contacts(_room()) == []


def test_door_links_only_from_explicit_knowledge_and_the_path_state() -> None:
    rooms = [_room("bad", sides={D: "inside", D2: "inside"}, contacts=(W, D, D2), connected={D: "flur", D2: "nirgends"}),
             _room("flur", contacts=(D2,), sides={D2: "inside"}), _room("kueche"), 7]
    links = cs.door_links(rooms)
    assert links == {frozenset({"bad", "flur"}): {D, D2}}                     # named room + the same contact in two rooms
    assert cs.door_links([cs.runtime_view(r) for r in rooms if isinstance(r, dict)]) == links
    assert cs.door_path(links, "bad", "flur", {D: "open", D2: "closed"}) == "open"
    assert cs.door_path(links, "flur", "bad", {D: "closed", D2: "closed"}) == "closed"
    assert cs.door_path(links, "bad", "flur", {D: "closed"}) is None          # one door unknown: no claim
    assert cs.door_path(links, "bad", "kueche", {}) is None                    # no knowledge at all


def test_prepare_runtime_rooms_reports_a_side_conflict_and_keeps_the_outside_behaviour() -> None:
    rooms, issues = prepare_runtime_rooms([_room("bad", sides={D: "inside"}, volume=20), _room("flur", contacts=(D,), volume=20)])
    assert issues == [f"contact:{D}:side_conflict:bad,flur"]
    assert [r["contacts"] for r in rooms] == [[W, D], [D]]
    rooms, issues = prepare_runtime_rooms([_room("bad", sides={D: "inside"}, volume=20)])
    assert issues == [] and rooms[0]["contacts"] == [W] and rooms[0]["_all_contacts"] == [W, D]


def test_a_side_conflict_creates_no_inside_connection_at_runtime() -> None:
    """Hotfix: the runtime view drops a conflicting inside classification – door_links must not bring it back."""
    stored = [_room("bad", sides={D: "inside"}, connected={D: "flur"}, volume=20), _room("flur", contacts=(D,), volume=20)]
    runtime, issues = prepare_runtime_rooms(stored)
    assert issues == [f"contact:{D}:side_conflict:bad,flur"] and runtime[0]["_inside_contacts"] == []
    assert cs.door_links(runtime) == {}                                        # before the hotfix: {bad, flur} via the stored side
    assert cs.door_path(cs.door_links(runtime), "bad", "flur", {D: "closed"}) is None   # the pair keeps its previous treatment


def test_an_inside_sensor_shared_by_three_rooms_links_no_pair_on_its_own() -> None:
    """Hotfix: one sensor in three rooms names no single physical pair; only a named connected room links."""
    three = [_room(k, contacts=(D,), sides={D: "inside"}) for k in ("bad", "flur", "kueche")]
    assert cs.door_links(three) == {} and cs.door_links([cs.runtime_view(r) for r in three]) == {}
    named = [_room("bad", contacts=(D,), sides={D: "inside"}, connected={D: "flur"}),
             _room("flur", contacts=(D,), sides={D: "inside"}), _room("kueche", contacts=(D,), sides={D: "inside"})]
    assert cs.door_links(named) == {frozenset({"bad", "flur"}): {D}}
    two = [_room(k, contacts=(D,), sides={D: "inside"}) for k in ("bad", "flur")]
    assert cs.door_links(two) == {frozenset({"bad", "flur"}): {D}}            # exactly two rooms: still one door between them


def test_f05_a_shared_sensor_with_a_different_named_room_joins_no_rooms_and_is_reported() -> None:
    """F05: shared by A and B (implicit A–B) but A names C – before: A–B and A–C at once; now: no link, a reported conflict."""
    rooms = [_room("a", contacts=(D,), sides={D: "inside"}, connected={D: "c"}, volume=20),
             _room("b", contacts=(D,), sides={D: "inside"}, volume=20), _room("c", contacts=(W,), volume=20)]
    assert cs.door_links(rooms) == {}
    assert cs.door_link_conflicts(rooms) == {D: [["a", "b"], ["a", "c"]]}
    runtime, issues = prepare_runtime_rooms(rooms)
    assert issues == [f"contact:{D}:door_link_conflict:a+b|a+c"] and cs.door_links(runtime) == {}
    agreeing = [_room("a", contacts=(D,), sides={D: "inside"}, connected={D: "b"}), _room("b", contacts=(D,), sides={D: "inside"}, connected={D: "a"})]
    assert cs.door_links(agreeing) == {frozenset({"a", "b"}): {D}} and cs.door_link_conflicts(agreeing) == {}
