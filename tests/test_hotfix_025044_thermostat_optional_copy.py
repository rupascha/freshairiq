import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/freshairiq"
FLOW = (COMP / "config_flow.py").read_text(encoding="utf-8")
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_thermostat_is_optional_in_all_native_room_schemas():
    for function, end in (("def _room_schema", "def _room_section_schema"), ("def _room_section_schema", "def _contact_reference_field")):
        block = FLOW[FLOW.index(function):FLOW.index(end, FLOW.index(function))]
        assert "_optional(CONF_ROOM_CLIMATE" in block
        assert "vol.Required(CONF_ROOM_CLIMATE" not in block


def test_room_normalisation_does_not_require_thermostat():
    block = FLOW[FLOW.index("def _normalise_room"):FLOW.index("def _normalise_legacy_entry_data", FLOW.index("def _normalise_room"))]
    assert 'errors[CONF_ROOM_CLIMATE]' not in block
    assert 'if not room.get(CONF_ROOM_CLIMATE)' not in block


def test_de_en_explain_optional_thermostat_and_target_sources():
    de = json.loads((COMP / "translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    de_text = json.dumps(de, ensure_ascii=False)
    en_text = json.dumps(en, ensure_ascii=False)
    assert "Freiwillige Eingabe. Ohne Thermostat/Klimagerät" in de_text
    assert "Optional input. The room" in en_text
    for token in ("Automatisch nutzt den Thermostat-Sollwert", "Manuell verwendet die unten eingestellte Zieltemperatur", "Fallback"):
        assert token in de_text


def test_dashboard_explains_optional_thermostat():
    assert "Freiwillige Eingabe. Ohne Thermostat/Klimagerät kann der Raum gespeichert" in CARD
    assert "Automatisch vom Thermostat" in CARD
    assert "Nur bei manueller Auswahl." in CARD
    assert "Fallback-Zieltemperatur" in CARD
