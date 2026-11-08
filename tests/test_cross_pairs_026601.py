"""v0.26.6.1 (#25): cross-ventilation pairs written with room names – one resolution for every reader."""
from __future__ import annotations

from custom_components.freshairiq import cross_pairs as cp
from custom_components.freshairiq.recommendation import _parse_pairs

ROOMS = [{"key": "schlafzimmer", "name": "Schlafzimmer"}, {"key": "wohnzimmer", "name": "Wohnzimmer"},
         {"key": "esszimmer", "name": "Esszimmer"}, {"key": "kuche", "name": "Küche"},
         {"key": "bad_og", "name": "Bad"}, {"key": "bad_eg", "name": "bad"}, {"key": "flur", "name": "Diele"}, "junk", {"name": "no key"}]


def test_the_reported_names_resolve_to_keys() -> None:
    pairs, problems = cp.parse("Schlafzimmer+Wohnzimmer,Esszimmer+Küche", ROOMS)
    assert problems == [] and cp.canonical(pairs) == "schlafzimmer+wohnzimmer,esszimmer+kuche"
    # case, umlauts, spaces, line breaks and semicolons as separators
    assert cp.canonical(cp.parse(" schlafZIMMER + WOHNZIMMER ;\nesszimmer+KÜCHE ", ROOMS)[0]) == "schlafzimmer+wohnzimmer,esszimmer+kuche"


def test_exact_key_first_then_unique_name_then_slug() -> None:
    assert cp.resolve_room("flur", ROOMS) == ("flur", None)              # key
    assert cp.resolve_room("Diele", ROOMS) == ("flur", None)             # name
    assert cp.resolve_room("kuche", ROOMS) == ("kuche", None)
    assert cp.resolve_room("Kueche", ROOMS) == (None, "unknown")         # the key convention folds ü to u, not ue
    assert cp.resolve_room("Bad", ROOMS) == (None, "ambiguous")          # two rooms named "Bad"/"bad"
    assert cp.resolve_room("bad_og", ROOMS) == ("bad_og", None)          # … the key still works
    assert cp.resolve_room("Wohn Zimmer", [{"key": "wohn_zimmer", "name": "Living"}]) == ("wohn_zimmer", None)   # slug of the key
    assert cp.resolve_room("", ROOMS) == (None, "unknown")
    assert cp.slug("Gäste-WC ß") == "gaste_wc_s"


def test_invalid_pairs_are_named_not_ignored() -> None:
    pairs, problems = cp.parse("Schlafzimmer+Dachboden, Bad+Flur, Wohnzimmer, a+b+c, Küche+kuche, Wohnzimmer+Esszimmer, esszimmer+wohnzimmer, +Flur", ROOMS)
    assert pairs == [("wohnzimmer", "esszimmer")]
    assert [(p["code"], p.get("room")) for p in problems] == [
        ("unknown", "Dachboden"), ("ambiguous", "Bad"), ("malformed", None), ("malformed", None), ("same", None), ("duplicate", None), ("malformed", None)]
    assert cp.parse("", ROOMS) == ([], []) and cp.parse(None, ROOMS) == ([], [])


def test_runtime_readers_use_the_same_resolution() -> None:
    assert _parse_pairs("Schlafzimmer+Wohnzimmer", ROOMS) == [("schlafzimmer", "wohnzimmer")]
    assert _parse_pairs("schlafzimmer+wohnzimmer") == []               # without rooms nothing is guessed
    assert cp.key_pairs("Schlafzimmer+Wohnzimmer, x+y", ROOMS) == [("schlafzimmer", "wohnzimmer")]
    assert cp.linked("Wohnzimmer+Esszimmer", ROOMS, "esszimmer", "wohnzimmer") is True
    assert cp.linked("Wohnzimmer+Esszimmer", ROOMS, "kuche", "wohnzimmer") is False


def test_migration_is_once_and_idempotent_and_keeps_what_it_cannot_resolve() -> None:
    options = {"cross_ventilation_pairs": "Schlafzimmer+Wohnzimmer,Esszimmer+Küche", "cross_zone_connections": "Wohnzimmer+Esszimmer", "other": 1}
    first, unresolved = cp.migrate(options, ROOMS)
    assert first == {"cross_ventilation_pairs": "schlafzimmer+wohnzimmer,esszimmer+kuche", "cross_zone_connections": "wohnzimmer+esszimmer", "other": 1}
    assert unresolved == []
    assert cp.migrate(first, ROOMS) == (first, [])                        # idempotent
    valid = {"cross_ventilation_pairs": "schlafzimmer+wohnzimmer", "cross_zone_connections": ""}
    assert cp.migrate(valid, ROOMS) == (valid, [])                        # valid key pairs stay exactly as they are
    broken = {"cross_ventilation_pairs": "Schlafzimmer+Wohnzimmer, Dachboden+Küche, Küche+Küche, Wohnzimmer+Schlafzimmer"}
    migrated, unresolved = cp.migrate(broken, ROOMS)
    assert migrated["cross_ventilation_pairs"] == "schlafzimmer+wohnzimmer,Dachboden+Küche,Küche+Küche"
    assert unresolved == ["cross_ventilation_pairs: Dachboden+Küche", "cross_ventilation_pairs: Küche+Küche"]
    assert cp.migrate(migrated, ROOMS) == (migrated, unresolved)          # again: nothing changes, the same is reported
    only_bad = {"cross_ventilation_pairs": "Dachboden+Keller"}
    assert cp.migrate(only_bad, ROOMS) == (only_bad, ["cross_ventilation_pairs: Dachboden+Keller"])
