"""Re-audit 0.26.5.5 (31.10.): display semantics of the three dashboard variants.

D01  The house map knows every house-aligned room code the backend can publish (ventilate_later,
     monitor_open were shown as "Unbekannt") – words in German and English and a tone.
D02  The house map hero knows every recommendation kind the backend can publish (pollen_wait,
     sensor, prepare fell back to a green check mark).
D03  The shared fixture of the display tests is exactly what opening_strategy publishes.
Presentation only: no decision is recomputed in the frontend.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import pytest

from custom_components.freshairiq.opening_strategy import HOUSE_ALIGNED_STATES, house_aligned_room_actions

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "freshairiq"
HOUSE_CARD = (PKG / "frontend" / "freshairiq-house-card.js").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "frontend_tests" / "fixtures" / "display_semantics.json").read_text(encoding="utf-8"))


def _object_keys(source: str, start: str) -> set[str]:
    """Keys of the JS object literal that follows ``start`` (one nesting level)."""
    begin = source.index(start) + len(start)
    depth, end = 1, begin
    while depth:
        depth += {"{": 1, "}": -1}.get(source[end], 0)
        end += 1
    return set(re.findall(r"(?:^|[,{\s])([a-z_]+):", source[begin:end - 1]))


def _backend_kinds() -> set[str]:
    """Every literal recommendation kind the integration can publish."""
    kinds: set[str] = set()
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "result" and node.args \
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                kinds.add(node.args[0].value)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                target = node.targets[0]
                if (isinstance(target, ast.Name) and target.id == "kind") or (
                        isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and target.slice.value == "kind"
                        and getattr(target.value, "id", "") in {"recommendation", "intelligent_recommendation", "out"}):
                    kinds.add(node.value.value)
    return kinds


def test_d01_every_house_aligned_code_has_words_and_a_tone() -> None:
    sections = HOUSE_CARD.split("\n  en: {")
    de_actions = _object_keys(sections[0], "actions: {")
    en_actions = _object_keys(sections[1], "actions: {")
    tones = _object_keys(HOUSE_CARD, "const TONE = {")
    for code in HOUSE_ALIGNED_STATES | {"unknown"}:
        assert code in de_actions and code in en_actions, code
    for code in HOUSE_ALIGNED_STATES:
        assert code in tones, code


def test_d02_every_backend_recommendation_kind_has_a_hero_tone() -> None:
    kinds = _backend_kinds()
    assert {"ventilate", "continue", "close", "wait", "prepare", "pollen_wait", "okay", "sensor"} <= kinds
    rec_tone = _object_keys(HOUSE_CARD, "const REC_TONE = {")
    assert kinds - {"home"} <= rec_tone, kinds - rec_tone  # "home" is the presence kind, not a recommendation


@pytest.mark.parametrize("name", sorted(FIXTURE["scenarios"]))
def test_d03_the_display_fixture_is_what_the_backend_publishes(name) -> None:
    scenario = FIXTURE["scenarios"][name]
    rooms = copy.deepcopy(scenario["rooms"])
    for room in rooms.values():
        room.pop("house_aligned_action")
    house_aligned_room_actions(copy.deepcopy(scenario["recommendation"]), rooms)
    assert {k: r["house_aligned_action"] for k, r in rooms.items()} == {k: r["house_aligned_action"] for k, r in scenario["rooms"].items()}
    assert _backend_kinds() >= {scenario["recommendation"]["kind"]}
