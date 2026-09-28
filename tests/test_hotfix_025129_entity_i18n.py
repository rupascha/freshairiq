from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_base_entity_does_not_override_translated_names():
    text = (ROOT / "custom_components/freshairiq/entity.py").read_text(encoding="utf-8")
    assert 'if getattr(self, "_attr_translation_key", None) is None:' in text
    assert text.count("self._attr_name = name") == 1

def test_operating_profile_has_no_hardcoded_attr_name():
    text = (ROOT / "custom_components/freshairiq/select.py").read_text(encoding="utf-8")
    assert '_attr_translation_key = "operating_profile"' in text
    assert '_attr_name = "Betriebsmodus"' not in text

def test_reported_entities_have_translation_keys_and_english_names():
    import json
    en = json.loads((ROOT / "custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8"))
    entity = en["entity"]
    expected = {
        ("select", "operating_profile"): "Operating mode",
        ("number", "forecast_horizon"): "Forecast horizon",
        ("number", "guest_adults"): "Adult overnight guests",
        ("number", "guest_children"): "Child overnight guests",
    }
    for (platform, key), name in expected.items():
        assert entity[platform][key]["name"] == name
