from pathlib import Path
from custom_components.freshairiq.opening_state import normalize_opening_state


def test_all_supported_aliases_have_one_canonical_meaning():
    expected = {
        "on": "open", "open": "open", "opening": "open", "opened": "open", "auf": "open",
        "tilted": "tilted", "tilt": "tilted", "kip": "tilted", "kipp": "tilted",
        "gekippt": "tilted", "vent": "tilted", "ventilation": "tilted",
        "off": "closed", "closed": "closed", "closing": "closed", "shut": "closed", "zu": "closed",
        "unknown": "unknown", "unavailable": "unknown", "none": "unknown", "": "unknown", "half_open": "unknown",
    }
    for raw, canonical in expected.items():
        assert normalize_opening_state(raw) == canonical, (raw, canonical)


def test_coordinator_uses_central_normalizer_for_close_and_restore_paths():
    text = Path("custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'normalized = normalize_opening_state(state.state)' in text
    assert 'if normalized in {"open", "tilted"}:' in text
    assert 'if normalized != "closed":' in text
    assert 'and normalize_opening_state(state.state) != "unknown"' in text
    assert 'normalize_opening_state(new_state.state) in {"closed", "open", "tilted"}' in text
    # Regression: no second hand-maintained opening-state set may remain in these paths.
    assert 'open_states = {"on", "open", "opening"' not in text
    assert 'new_state.state not in {"on", "open", "opening"' not in text


def test_aliases_that_start_sessions_cannot_be_misread_as_closed():
    active_aliases = ["on", "open", "opening", "opened", "auf", "tilted", "tilt", "kip", "kipp", "gekippt", "vent", "ventilation"]
    assert all(normalize_opening_state(raw) in {"open", "tilted"} for raw in active_aliases)
    assert all(normalize_opening_state(raw) != "closed" for raw in active_aliases)
