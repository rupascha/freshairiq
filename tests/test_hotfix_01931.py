from datetime import datetime, timedelta, timezone
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_details_uses_compact_last_ventilation_tile_before_full_result():
    card = (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
    assert "_lastVentilationTile(last)" in card
    assert 'class="last-vent-tile clickable" data-info="lastvent"' in card
    assert 'const lastCard = this._lastVentilationTile(last);' in card
    assert 'LÜFTUNGSERGEBNIS · DAUERHAFT GESPEICHERT' in card


def test_close_confirmation_is_fixed_three_seconds_and_reopen_keeps_active_session():
    const = (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    coordinator = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "SESSION_CLOSE_CONFIRM_SECONDS = 3.0" in const
    assert "if is_open:\n                    session_should = True" in coordinator
    assert "closed_for < SESSION_CLOSE_CONFIRM_SECONDS" in coordinator
    assert "async_call_later(\n                    self.hass, SESSION_CLOSE_CONFIRM_SECONDS, _confirm_close" in coordinator


def test_close_confirmation_helper_respects_any_and_all_contact_modes():
    # Parse/extract the pure helper so this regression test stays independent of
    # a full Home Assistant runtime.
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    helper = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_room_closed_for_seconds")
    mini = ast.Module(body=[helper], type_ignores=[])
    ast.fix_missing_locations(mini)
    ns = {
        "Any": object,
        "HomeAssistant": object,
        "datetime": datetime,
        "CONF_CONTACT_MODE": "contact_mode",
        "CONTACT_MODE_ANY": "any",
        "CONTACT_MODE_ALL": "all",
        "_contact_ids": lambda room: room["contacts"],
    }
    exec(compile(mini, "<helper>", "exec"), ns)
    fn = ns["_room_closed_for_seconds"]

    class State:
        def __init__(self, state, last_changed):
            self.state = state
            self.last_changed = last_changed

    class States:
        def __init__(self, values): self.values = values
        def get(self, entity_id): return self.values.get(entity_id)

    class Hass:
        def __init__(self, values): self.states = States(values)

    now = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)
    values = {
        "a": State("off", now - timedelta(seconds=8)),
        "b": State("off", now - timedelta(seconds=2)),
    }
    assert fn(Hass(values), {"contacts": ["a", "b"], "contact_mode": "any"}, now) == 2
    assert fn(Hass(values), {"contacts": ["a", "b"], "contact_mode": "all"}, now) == 8
    values["b"] = State("on", now - timedelta(seconds=1))
    assert fn(Hass(values), {"contacts": ["a", "b"], "contact_mode": "any"}, now) is None
    assert fn(Hass(values), {"contacts": ["a", "b"], "contact_mode": "all"}, now) == 8
