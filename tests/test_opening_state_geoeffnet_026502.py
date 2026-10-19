"""0.26.5.2 (support case, bedroom template): a user template reports
"geöffnet / gekippt / geschlossen". "geöffnet" was normalised to "unknown", so a
running tilt was kept and the learning session was quarantined (FAIQ-OPENING-3STATE-006)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.freshairiq.opening_state import advertises_three_states, normalize_opening_state


@pytest.mark.parametrize("raw", ["geöffnet", "Geöffnet", "GEÖFFNET", "  geöffnet\n", "\n  geöffnet  \n"])
def test_geoeffnet_is_open(raw):
    assert normalize_opening_state(raw) == "open"


@pytest.mark.parametrize("raw, expected", [
    ("gekippt", "tilted"), ("  Gekippt\n", "tilted"), ("geschlossen", "closed"), ("  geschlossen\n", "closed"),
    ("offen", "open"), ("open", "open"), ("on", "open"), ("auf", "open"),
    ("off", "closed"), ("zu", "closed"), ("tilted", "tilted"), ("kipp", "tilted"),
    ("unknown", "unknown"), ("unavailable", "unknown"), ("", "unknown"), (None, "unknown"), ("geoeffnet?", "unknown"),
])
def test_existing_aliases_are_unchanged(raw, expected):
    assert normalize_opening_state(raw) == expected


def test_the_template_vocabulary_is_a_three_state_option_list():
    state = SimpleNamespace(state="geschlossen", attributes={"options": ["geöffnet", "gekippt", "geschlossen"]})
    assert advertises_three_states("sensor.fenster_schlafzimmer", state)
    assert not advertises_three_states("binary_sensor.fenster_schlafzimmer", state)
