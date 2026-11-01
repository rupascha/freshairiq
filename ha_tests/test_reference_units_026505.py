"""0.26.5.5 (community diagnosis 28.10.): laundry room reference air of 2.10 g/m³.

The laundry room draws its air from the hallway (9.79 g/m³ absolute humidity), but its
model used 2.10 g/m³ – exactly what 9.79 read as *percent* relative humidity at about
24 °C gives. A humidity sensor that states another unit (an absolute-humidity sensor in
g/m³) is no relative humidity: the pair is not used (no outdoor fallback) and the room
says why. Correct %-sensors, unavailable values and opening-specific pairs keep their rules.
"""
from __future__ import annotations

from datetime import timedelta

from custom_components.freshairiq.model import absolute_humidity
from ha_tests.test_cov_setup_and_platforms import _entry, _setup, _unload
from ha_tests.test_fan_automation_026504 import START, _bath, _switch


async def _laundry(hass, freezer, *, hall_humidity: str, unit: str | None):
    freezer.move_to(START)
    _switch(hass, [])
    hass.states.async_set("sensor.outdoor_temperature", "12", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outdoor_humidity", "85", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.bad_temperature", "24", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.bad_humidity", "53.5", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.flur_t", "23.8", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.flur_h", hall_humidity, {"unit_of_measurement": unit} if unit else {})
    hass.states.async_set("binary_sensor.bad_fenster", "off", {"device_class": "window"})
    hass.states.async_set("switch.bad_luefter", "on")
    entry = await _setup(hass, _entry(rooms=[_bath("recommendation")]))
    for _ in range(2):
        freezer.tick(timedelta(seconds=30))
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    return entry, entry.runtime_data.data["rooms"]["bad"]


async def test_absolute_humidity_sensor_is_not_read_as_percent(hass, freezer) -> None:
    entry, room = await _laundry(hass, freezer, hall_humidity="9.79", unit="g/m³")
    assert room["reference_path"] == "neighbour_room"
    # before: 9.79 "%" at 23.8 °C → about 2.1 g/m³ supply air, the airing looked far too effective
    assert round(absolute_humidity(23.8, 9.79), 1) == 2.1
    assert room["reference_humidity"] is None or room["reference_humidity"] > 5
    assert room["reference_unit_issue"] == {"role": "neighbour_room_humidity", "unit": "g/m³"}
    assert any("does not report relative humidity" in reason for reason in room["recommendation_reasons"])
    # the pair fails closed: never the outdoor air instead
    assert room["reference_humidity"] != round(absolute_humidity(12, 85), 2)
    record = entry.runtime_data.diagnostics._build_record(entry.runtime_data.data, entry.runtime_data.store.data, START, [], "test")
    exported = next(r for r in record["rooms"] if r["key"] == "bad")
    assert exported["reference_unit_issue"] == {"role": "neighbour_room_humidity", "unit": "g/m³"}
    await _unload(hass, entry)


async def test_a_percent_sensor_and_a_sensor_without_unit_are_used(hass, freezer) -> None:
    for unit in ("%", None):
        entry, room = await _laundry(hass, freezer, hall_humidity="45", unit=unit)
        assert room["reference_path"] == "neighbour_room"
        assert room["reference_humidity"] == round(absolute_humidity(23.8, 45), 2)
        assert room.get("reference_unit_issue") is None
        await _unload(hass, entry)


async def test_an_opening_specific_humidity_in_grams_fails_closed(hass, freezer) -> None:
    from ha_tests.test_door_delay_cooling_026504 import HUM, _rooms, _settled

    rooms = _rooms(flur_delay=0)
    d = await _settled(hass, freezer, rooms, initial={"sensor.flurref_h": ("9.79", {**HUM, "unit_of_measurement": "g/m³"})})
    await d.step(30, binary_sensor__flur_tuer="on")
    await d.step(30)
    assert d.room("flur")["reference_humidity"] is None  # never 9.79 "%" and never the outdoor air
    assert d.room("flur")["action"] == "Check sensor"


async def test_f02_a_wrong_unit_behind_a_valid_source_is_not_hidden(hass, freezer) -> None:
    """Two openings open at once: one source in g/m³, the other a valid % sensor (F02).

    Before, the g/m³ value (9.79 read as %) was simply outranked by the moister valid source.
    The incoming air is unknown then – no value, never the outdoor air.
    """
    from ha_tests.test_door_delay_cooling_026504 import HUM, _rooms, _settled, _with_reference

    rooms = _rooms(flur_contacts=("binary_sensor.flur_tuer", "binary_sensor.flur_fenster"), flur_delay=0)
    _with_reference(rooms[1], "binary_sensor.flur_fenster", "sensor.badref_t", "sensor.badref_h", 0)
    d = await _settled(hass, freezer, rooms, initial={"sensor.flurref_h": ("9.79", {**HUM, "unit_of_measurement": "g/m³"}),
                                                       "sensor.badref_h": ("70", HUM)})
    await d.step(30, binary_sensor__flur_tuer="on", binary_sensor__flur_fenster="on")
    await d.step(30)
    assert d.room("flur")["reference_humidity"] is None
    assert d.room("flur")["action"] == "Check sensor"


async def test_the_chosen_default_pair_is_unit_checked_too(hass) -> None:
    from custom_components.freshairiq.coordinator_contacts import _unit_checked_reference

    hass.states.async_set("sensor.ref_ah", "9.8", {"unit_of_measurement": "g/m³"})
    hass.states.async_set("sensor.ref_rh", "55", {"unit_of_measurement": "%"})
    assert _unit_checked_reference(hass, ("sensor.t", "sensor.ref_ah", 18.0, 9.8)) == ("sensor.t", "sensor.ref_ah", None, None)
    assert _unit_checked_reference(hass, ("sensor.t", "sensor.ref_rh", 18.0, 55.0)) == ("sensor.t", "sensor.ref_rh", 18.0, 55.0)
