"""v0.25.4.9 regression: shutter/blind position must not contaminate learning."""
import json
from pathlib import Path
from types import SimpleNamespace
from tests.frontend_source import card_text

ROOT = Path(__file__).resolve().parents[1]


def _load_helper():
    import ast
    source = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_cover_learning_guard"]
    module = ast.Module(body=nodes, type_ignores=[])
    ns = {"Any": object, "HomeAssistant": object, "CONF_CONTACT_COVERS": "contact_covers", "finite_float": lambda v: float(v) if v is not None else None}
    exec(compile(module, "coordinator.py", "exec"), ns)
    return ns["_cover_learning_guard"]


class States:
    def __init__(self, positions): self.positions = positions
    def get(self, entity_id):
        value = self.positions.get(entity_id)
        return None if value is None else SimpleNamespace(attributes={"current_position": value})


def test_default_ha_direction_boundary_20_allowed_21_blocked():
    guard = _load_helper(); room={"contact_covers":{"binary_sensor.window":["cover.blind"]}}
    hass=SimpleNamespace(states=States({"cover.blind":80}))
    assert guard(hass,room,{"binary_sensor.window":"open"},{"cover_position_zero_means":"closed","cover_learning_max_closed_percent":20})["blocked"] is False
    hass.states=States({"cover.blind":79})
    out=guard(hass,room,{"binary_sensor.window":"open"},{"cover_position_zero_means":"closed","cover_learning_max_closed_percent":20})
    assert out["blocked"] is True and out["affected"][0]["closed_percent"] == 21


def test_inverted_direction_boundary_and_closed_contact_ignored():
    guard = _load_helper(); room={"contact_covers":{"binary_sensor.window":["cover.blind"]}}
    hass=SimpleNamespace(states=States({"cover.blind":20}))
    assert guard(hass,room,{"binary_sensor.window":"open"},{"cover_position_zero_means":"open","cover_learning_max_closed_percent":20})["blocked"] is False
    hass.states=States({"cover.blind":21})
    assert guard(hass,room,{"binary_sensor.window":"open"},{"cover_position_zero_means":"open","cover_learning_max_closed_percent":20})["blocked"] is True
    assert guard(hass,room,{"binary_sensor.window":"closed"},{"cover_position_zero_means":"open","cover_learning_max_closed_percent":20})["blocked"] is False


def test_unknown_position_does_not_invent_blockage_but_is_reported():
    guard = _load_helper(); room={"contact_covers":{"binary_sensor.window":["cover.blind"]}}
    out=guard(SimpleNamespace(states=States({})),room,{"binary_sensor.window":"open"},{"cover_position_zero_means":"closed","cover_learning_max_closed_percent":20})
    assert out["blocked"] is False and out["unknown"] == ["cover.blind"]


def test_contract_defaults_and_bilingual_explanations_present():
    const=(ROOT/"custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    contract=(ROOT/"custom_components/freshairiq/settings_contract.py").read_text(encoding="utf-8")
    assert '"cover_position_zero_means": "closed"' in const
    assert '"cover_learning_max_closed_percent": 20.0' in const
    assert '"cover_position_zero_means"' in contract and '"cover_learning_max_closed_percent"' in contract
    de=json.loads((ROOT/"custom_components/freshairiq/translations/de.json").read_text())
    en=json.loads((ROOT/"custom_components/freshairiq/translations/en.json").read_text())
    assert de["selector"]["cover_position_zero_means"]["options"]["closed"].startswith("0 % = vollständig geschlossen")
    assert en["selector"]["cover_position_zero_means"]["options"]["closed"].startswith("0 % = fully closed")
    assert "Lern-Grenze" in card_text()
