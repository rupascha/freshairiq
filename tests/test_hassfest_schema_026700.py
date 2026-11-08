"""0.26.7.0 hassfest hotfix: the translation files and the integration follow hassfest's rules.

Reproduced from the failed hassfest run: ``options.selector``, ``options.step.*.section`` (instead of ``sections``),
``config_subentries.room.entry_type`` missing, and the ``config_schema`` notice (``async_setup`` without
``CONFIG_SCHEMA``). The rules below are those of home-assistant/core ``script/hassfest/translations.py`` and
``config_schema.py`` for the parts FreshAirIQ uses.
"""
from __future__ import annotations

import ast
import json
import re
import string
from pathlib import Path

COMP = Path(__file__).resolve().parents[1] / "custom_components" / "freshairiq"
FILES = ("strings.json", "translations/en.json", "translations/de.json")
STEP_KEYS = {"title", "description", "data", "data_description", "menu_options", "menu_option_descriptions", "submit", "sections"}
SECTION_KEYS = {"data", "data_description", "description", "name"}
FLOW_KEYS = {"flow_title", "step", "error", "abort", "progress", "create_entry", "initiate_flow", "title"}
RE_URL = re.compile(r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5):\/\/|www\.)[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?)", re.I)


def _flow_problems(name: str, flow: dict, subentry: bool = False) -> list[str]:
    problems = [f"{name}.{key}" for key in flow if key not in FLOW_KEYS | ({"entry_type"} if subentry else set())]
    if subentry and ("entry_type" not in flow or "user" not in flow.get("initiate_flow", {})):
        problems.append(f"{name}: entry_type and initiate_flow.user are required")
    for step_id, step in flow.get("step", {}).items():
        for key, value in step.items():
            if key not in STEP_KEYS:
                problems.append(f"{name}.step.{step_id}.{key}")
            if key == "sections":
                problems += [f"{name}.step.{step_id}.sections.{sec}.{k}" for sec, body in value.items() for k in body if k not in SECTION_KEYS]
    return problems


def _strings(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}" if path else key)
    elif isinstance(node, str):
        yield path, node


def test_config_options_and_subentry_translations_follow_the_hassfest_schema() -> None:
    for name in FILES:
        data = json.loads((COMP / name).read_text(encoding="utf-8"))
        problems = _flow_problems("config", data["config"]) + _flow_problems("options", data["options"])
        for sub, flow in data.get("config_subentries", {}).items():
            problems += _flow_problems(f"config_subentries.{sub}", flow, subentry=True)
        assert problems == [], name


def test_every_translation_value_is_valid_and_german_and_english_match() -> None:
    texts = {}
    for name in FILES:
        texts[name] = dict(_strings(json.loads((COMP / name).read_text(encoding="utf-8"))))
        for path, value in texts[name].items():
            fields = {f for _, f, _, _ in string.Formatter().parse(value) if f}
            assert all(f.isidentifier() for f in fields), (name, path)
            assert value == value.strip() and not re.search(r"<[a-z].*?>", value, re.I) and not RE_URL.search(value), (name, path)
            assert not re.search(r"(.+\[%)|(%\].+)", value) and not re.search(r"'{\w+}'", value), (name, path)
    en, de = texts["translations/en.json"], texts["translations/de.json"]
    assert texts["strings.json"] == en
    assert set(en) == set(de)
    place = lambda v: {f for _, f, _, _ in string.Formatter().parse(v) if f}  # noqa: E731
    assert [k for k in en if place(en[k]) != place(de[k])] == []


def test_the_room_subentry_names_its_type_and_the_form_sections_exist_in_the_flows() -> None:
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    assert (de["config_subentries"]["room"]["entry_type"], en["config_subentries"]["room"]["entry_type"]) == ("Raum", "Room")
    source = "\n".join(p.read_text(encoding="utf-8") for p in COMP.glob("config_flow*.py"))
    assert 'return {"room": FreshAirIQRoomSubentryFlow}' in source
    used = set(re.findall(r'vol\.(?:Required|Optional)\("([a-z_]+)"\)\s*:\s*section\(', source))
    shown = {sec for step in de["options"]["step"].values() for sec in step.get("sections", {})}
    assert used and used <= shown
    keys = set(re.findall(r'translation_key="([a-z_]+)"', source))
    assert keys and keys <= set(de["selector"]) and "selector" not in de["options"]


def test_async_setup_comes_with_a_config_entry_only_schema() -> None:
    module = ast.parse((COMP / "__init__.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.AsyncFunctionDef) and n.name == "async_setup" for n in module.body)
    schema = [n for n in module.body if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "CONFIG_SCHEMA" for t in n.targets)]
    assert len(schema) == 1 and ast.unparse(schema[0].value) == "cv.config_entry_only_config_schema(DOMAIN)"
