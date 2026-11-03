"""Hotfix 0.26.6.0 (4): the house map finds the guest settings like the FreshAirIQ dashboard card.

Contract between the integration and both cards: every FreshAirIQ entity publishes ``freshairiq_entry_id``
and ``freshairiq_entity_key``; the guest numbers use the keys ``guest_adults`` / ``guest_children`` with the
range 0–20. Both cards resolve the entity by these attributes and the card's config entry (not by name or by
the first FreshAirIQ entity found), and clamp to 0–20. The behaviour is tested in frontend_tests/house.spec.mjs.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_the_integration_publishes_the_stable_identity_of_the_guest_numbers() -> None:
    entity, number = _source("entity.py"), _source("number.py")
    assert '"freshairiq_entry_id": self._entry.entry_id' in entity and '"freshairiq_entity_key": self._key' in entity
    for key in ("guest_adults", "guest_children"):
        block = number[number.index(f'"{key}", '):][:200]
        assert block.startswith(f'"{key}", ')
    assert number.count("_attr_native_max_value = 20") >= 2 and "min(max(float(value), 0.0), 20.0)" in number


def test_both_cards_resolve_the_guest_number_by_entity_key_and_config_entry() -> None:
    dashboard = _source("frontend/freshairiq-card.js")
    house = _source("frontend/freshairiq-house-card.js")
    for source in (dashboard, house):
        assert "freshairiq_entity_key === key" in source.replace("a.freshairiq_entity_key", "freshairiq_entity_key").replace("st.attributes.freshairiq_entity_key", "freshairiq_entity_key")
        assert re.search(r"freshairiq_entry_id === entry(Id)?", source)
        assert "Math.min(20" in source
