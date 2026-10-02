"""Regression guards for v0.25.2.21 room-wizard reload hotfix."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


def _options_method(name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FreshAirIQOptionsFlow")
    return next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def test_room_wizard_defers_structural_reload_until_final_step() -> None:
    for name in ("async_step_add_room", "async_step_edit_room", "async_step_contact_orientations", "async_step_contact_delays"):
        src = ast.unparse(_options_method(name))
        assert "_persist_working_state(reload_entry=False)" in src, name

    refs = ast.unparse(_options_method("async_step_contact_references"))
    assert "_persist_working_state(reload_entry=False)" in refs
    assert "_persist_working_state(reload_entry=True)" in refs


def test_contactless_room_finishes_without_contact_metadata_forms_and_reloads_once() -> None:
    src = ast.unparse(_options_method("async_step_contact_orientations"))
    assert "if not contacts:" in src
    assert "_persist_working_state(reload_entry=True)" in src
    assert "return await self.async_step_rooms()" in src


def test_contacts_remain_optional_in_room_schema_and_normaliser() -> None:
    schema = ast.unparse(next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.FunctionDef) and n.name == "_room_section_schema"))
    normalise = ast.unparse(next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.FunctionDef) and n.name == "_normalise_room"))
    assert "vol.Optional(CONF_ROOM_CONTACTS" in schema
    assert 'errors[CONF_ROOM_CONTACTS]' not in normalise
