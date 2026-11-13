"""0.26.7.0 support case A: three-room chains in the cross-ventilation pairs.

"Wohnzimmer+Flur+Schlafzimmer" is an air path, not a pair. It is never guessed into pairs (the hall has no window,
a pair with it could never be active), it is kept as written, and both the options flow and the repair notice say
what to enter instead: the two window rooms as the pair and the room in between as an open connection.
"""
from __future__ import annotations

from custom_components.freshairiq import cross_pairs as cp


ROOMS = [{"key": "wohnzimmer", "name": "Wohnzimmer"}, {"key": "schlafzimmer", "name": "Schlafzimmer"},
         {"key": "arbeitszimmer", "name": "Arbeitszimmer"}, {"key": "flur", "name": "Flur"}]
CHAINS = "Wohnzimmer+Flur+Schlafzimmer,Wohnzimmer+Flur+Arbeitszimmer,Arbeitszimmer+Flur+Schlafzimmer"


def test_chains_are_named_not_guessed():
    pairs, problems = cp.parse(CHAINS, ROOMS)
    assert pairs == []
    assert [(p["code"], p["chain"], p["ends"], p["middle"]) for p in problems] == [
        ("malformed", True, "Wohnzimmer+Schlafzimmer", "Flur"),
        ("malformed", True, "Wohnzimmer+Arbeitszimmer", "Flur"),
        ("malformed", True, "Arbeitszimmer+Schlafzimmer", "Flur")]


def test_message_says_what_to_enter_in_both_languages():
    problems = cp.parse("Wohnzimmer+Flur+Schlafzimmer", ROOMS)[1]
    de = cp.describe(problems, "de")
    assert "nennt mehr als zwei Räume" in de and "Wohnzimmer+Schlafzimmer" in de and "(Flur)" in de and "Offene Verbindungen" in de
    en = cp.describe(problems, "en")
    assert "names more than two rooms" in en and "Wohnzimmer+Schlafzimmer" in en and "Open connections" in en
    # a two-room typo keeps the old wording
    assert cp.describe(cp.parse("Wohnzimmer", ROOMS)[1], "de") == "„Wohnzimmer“ ist kein Raumpaar (Form: Raum+Raum)"


def test_stored_chains_stay_unchanged_and_are_reported():
    options = {"cross_ventilation_pairs": CHAINS}
    migrated, unresolved = cp.migrate(options, ROOMS)
    assert migrated["cross_ventilation_pairs"] == CHAINS          # nothing destroyed
    assert len(unresolved) == 3
    assert len(cp.unusable(migrated, ROOMS)) == 3                 # -> repair notice
    assert cp.unusable({"cross_ventilation_pairs": "wohnzimmer+schlafzimmer"}, ROOMS) == []
    # a valid pair next to a chain is used, the chain is kept and named
    mixed = cp.migrate({"cross_ventilation_pairs": "Wohnzimmer+Schlafzimmer,Wohnzimmer+Flur+Arbeitszimmer"}, ROOMS)[0]
    assert mixed["cross_ventilation_pairs"] == "wohnzimmer+schlafzimmer,Wohnzimmer+Flur+Arbeitszimmer"
    assert cp.key_pairs(mixed["cross_ventilation_pairs"], ROOMS) == [("wohnzimmer", "schlafzimmer")]
