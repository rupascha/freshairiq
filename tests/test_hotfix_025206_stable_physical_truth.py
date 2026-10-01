from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / "custom_components/freshairiq/coordinator.py"


def _source() -> str:
    return COORD.read_text(encoding="utf-8")


def test_cross_ventilation_consumes_persisted_stable_three_state_truth():
    src = _source()
    assert 'room_mem.get("stable_opening_modes")' in src
    assert 'contact_modes=stable_modes, contact_since=stable_since' in src


def test_orientation_consumes_physical_contact_modes():
    src = _source()
    assert 'def _room_orientation_factor' in src
    assert 'contact_modes: dict[str, str] | None = None' in src
    assert 'contact_modes=physical_contact_modes' in src


def test_contact_reference_is_re_resolved_from_stable_physical_truth():
    src = _source()
    assert 'physical_contact_modes = {' in src
    assert 'contact_modes=physical_contact_modes' in src
    # The active-contact reference audit must use the same truth too.
    assert 'physical_contact_modes.get(_cid) in {"open", "tilted"}' in src


def test_binary_contacts_remain_immediate_in_physical_truth_map():
    src = _source()
    assert '("open" if _open_seconds(self.hass, c, now) is not None else "closed")' in src


def test_no_cross_call_uses_room_ventilation_without_stable_overrides():
    tree = ast.parse(_source())
    method = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_cross_ventilation_active"
    )
    calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_room_ventilation_state"]
    assert calls
    for call in calls:
        kw = {k.arg for k in call.keywords}
        assert {"contact_modes", "contact_since"} <= kw

def test_opening_assessment_display_uses_same_physical_truth():
    src = _source()
    assert 'contact_modes: dict[str, str] | None = None' in src
    assert '"is_open": ((contact_modes or {}).get(contact) in {"open", "tilted"})' in src
    assert 'wind_speed=wind_speed, contact_modes=physical_contact_modes' in src
