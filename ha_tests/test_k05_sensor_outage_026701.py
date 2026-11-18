"""K05 (0.26.7.1): a sensor outage never becomes 0 °C / 0 % / 0 ppm; the room keeps a reason and is evaluated again.

Real coordinator, bath temperature/humidity and kitchen CO2 go ``unavailable`` / ``unknown`` and come back.
"""
from __future__ import annotations

from ha_tests.test_cov_coordinator_b import CO2, HUM, TEMP, _cleanup_coordinators, _make  # noqa: F401


async def test_unavailable_room_sensors_give_a_reason_not_zeros_and_recover(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60)
    assert d.room("bad")["data_quality"] == "ok"
    await d.step(60, sensor__bad_t=("unavailable", TEMP), sensor__bad_h=("unknown", HUM))
    for _ in range(3):
        await d.step(60)
    room = d.room("bad")
    assert "bad" in d.data["rooms"]                                  # never silently removed
    assert room["data_quality"] != "ok" and room["action"] == "Check sensor", room["action"]
    assert room.get("reason")                                         # a readable reason
    for key in ("temperature", "humidity", "absolute_humidity"):
        assert room.get(key) in (None,) or room.get(key) != 0, (key, room.get(key))
    assert room.get("temperature") != 0.0 and room.get("humidity") != 0.0
    await d.step(60, sensor__bad_t=(23.4, TEMP), sensor__bad_h=(79.0, HUM))
    await d.step(60)
    room = d.room("bad")
    assert room["data_quality"] == "ok" and room["action"] != "Check sensor"
    assert room["temperature"] == 23.4 and room["humidity"] == 79.0


async def test_unavailable_co2_is_no_zero_ppm_and_no_reached_goal(hass, freezer) -> None:
    d = await _make(hass, freezer)
    await d.step(60)
    await d.step(60, sensor__kueche_co2=("unavailable", CO2))
    await d.step(60)
    kitchen = d.room("kueche")
    assert kitchen.get("co2") is None or kitchen.get("co2") != 0
    goal = next((g for g in kitchen["goal_state"]["goals"] if g["id"] == "co2"), None)
    assert goal is None or not (goal["reached"] and goal["value"] in (0, 0.0))
    await d.step(60, sensor__kueche_co2=(1180, CO2))
    await d.step(60)
    assert d.room("kueche")["co2"] == 1180
