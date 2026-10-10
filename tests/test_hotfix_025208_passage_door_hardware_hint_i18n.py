from pathlib import Path
import json
from tests.frontend_source import card_text
ROOT = Path(__file__).resolve().parents[1]

def test_devices_services_passage_option_is_precise_and_bilingual():
    de = json.loads((ROOT / "custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8"))
    base = json.loads((ROOT / "custom_components/freshairiq/strings.json").read_text(encoding="utf-8"))
    de_blob, en_blob, base_blob = (json.dumps(x, ensure_ascii=False) for x in (de,en,base))
    assert "Tür wird als Durchgang genutzt und von außen zugezogen" in de_blob
    assert "echter Drei-Zustands-Sensor" in de_blob and "Nicht für Drei-Zustands-Helfer" in de_blob
    assert "Door is used as a passage and pulled shut from outside" in en_blob
    assert "genuine three-state sensor" in en_blob and "Do not enable this option for three-state helpers" in en_blob
    assert "genuine three-state sensor" in base_blob

def test_dashboard_passage_option_has_same_hardware_warning_and_english_bridge():
    ui = card_text()
    for text in ("Tür wird als Durchgang genutzt und von außen zugezogen", "echter Drei-Zustands-Sensor am Türbeschlag", "Nicht für Drei-Zustands-Helfer", "Door is used as a passage and pulled shut from outside", "genuine three-state sensor on the door hardware", "Do not enable this option for three-state helpers"):
        assert text in ui

def test_passage_logic_and_storage_contract_unchanged():
    cfg = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    coord = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert "CONF_CONTACT_PASSAGE_DOORS" in cfg
    assert "proven_three_state" in coord and "active_passage_contacts" in coord and "passage_behavior" in coord
