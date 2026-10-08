from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _assert_translation_before_super(path: str, translation_stmt: str, super_fragment: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    translation_pos = text.index(translation_stmt)
    super_pos = text.index(super_fragment, translation_pos)
    assert translation_pos < super_pos


def test_dynamic_sensor_translation_keys_are_set_before_base_constructor():
    text = (ROOT / "custom_components/freshairiq/sensor.py").read_text(encoding="utf-8")
    house = text[text.index("class HouseSensor"):text.index("class RoomSensor")]
    room = text[text.index("class RoomSensor"):]
    assert house.index("self._attr_translation_key = desc.key") < house.index("super().__init__(coordinator, entry, desc.key, desc.name)")
    assert room.index("self._attr_translation_key = field") < room.index("super().__init__(")


def test_binary_sensor_translation_keys_are_set_before_base_constructor():
    text = (ROOT / "custom_components/freshairiq/binary_sensor.py").read_text(encoding="utf-8")
    cross = text[text.index("class CrossVentilationSensor"):text.index("class RoomCloseSensor")]
    close = text[text.index("class RoomCloseSensor"):]
    assert cross.index('self._attr_translation_key = "cross_ventilation"') < cross.index("super().__init__(")
    assert close.index('self._attr_translation_key = "close_recommended"') < close.index("super().__init__(")


def test_reported_room_entities_have_german_and_english_names():
    import json
    de = json.loads((ROOT / "custom_components/freshairiq/translations/de.json").read_text(encoding="utf-8"))["entity"]
    en = json.loads((ROOT / "custom_components/freshairiq/translations/en.json").read_text(encoding="utf-8"))["entity"]
    expected = {
        ("sensor", "absolute_humidity"): ("Absolute Feuchte", "Absolute humidity"),
        ("sensor", "action"): ("Aktion", "Action"),
        ("binary_sensor", "close_recommended"): ("Schließen empfohlen", "Close recommended"),
        ("sensor", "forecast_confidence"): ("Prognosesicherheit", "Forecast confidence"),
        ("sensor", "forecast_moisture_effect_ml"): ("Prognostizierte Feuchtewirkung", "Forecast moisture effect"),
        ("sensor", "forecast_cost"): ("Prognostizierte Wiederaufheizkosten", "Forecast reheating cost"),
        ("sensor", "forecast_temperature_change_c"): ("Prognostizierte Temperaturänderung", "Forecast temperature change"),
        ("sensor", "delta_g_m3"): ("Feuchtedifferenz", "Humidity difference"),
        ("sensor", "surface_rh"): ("Geschätzte Oberflächenfeuchte", "Estimated surface humidity"),
    }
    for (platform, key), (de_name, en_name) in expected.items():
        assert de[platform][key]["name"] == de_name
        assert en[platform][key]["name"] == en_name
