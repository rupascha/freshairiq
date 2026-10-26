"""0.26.5.4 (review A07): a CO2 airing in the real coordinator – asked for, carried out, ended.

The kitchen (1180 ppm, warning 1000 ppm, room not humid) is asked to air for CO2.
Once the window is open and CO2 falls below the warning threshold minus 50 ppm,
the airing is no longer kept open for CO2. The CO2 airing does not touch the
humidity hysteresis of the room.
"""
from __future__ import annotations

from ha_tests.test_cov_coordinator_b import CO2, OPTIONS, _cleanup_coordinators, _make  # noqa: F401


async def _airing(hass, freezer, thermostat_target: float):
    climate = ("heat", {"temperature": thermostat_target, "current_temperature": 22.1, "hvac_action": "heating"})
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400}, initial={"climate.kueche": climate})
    for _ in range(3):
        await d.step(60)
    kitchen = d.room("kueche")
    assert kitchen["action"] == "Ventilate" and kitchen["recommendation_reasons"][0].startswith("CO₂ 1180 ppm")
    assert d.mem("kueche")["ventilation_candidate_latched"] is False  # the humidity hysteresis stays untouched
    await d.step(60, binary_sensor__kueche_fenster="on")
    assert d.mem("kueche")["session_active"] is True
    actions = []
    for i, co2 in enumerate((1100, 1020, 960, 930, 900, 880, 860, 850, 840, 830, 820, 810)):
        await d.step(60, sensor__kueche_co2=(co2, CO2), sensor__kueche_h=round(61 - 0.2 * (i + 1), 1))
        actions.append((co2, d.room("kueche")["action"], d.room("kueche")["close_recommended"]))
    return d, actions


async def test_kitchen_co2_airing_from_request_to_close(hass, freezer) -> None:
    d, actions = await _airing(hass, freezer, thermostat_target=23.0)  # no cooling needed
    assert d.mem("kueche")["session_co2_only"] is True
    # kept open while CO2 is high (incl. the 50 ppm hysteresis band), closed once it is down
    assert all(action != "Close" for co2, action, _ in actions if co2 >= 960), actions
    assert any(action == "Close" or close for co2, action, close in actions if co2 < 950), actions


async def test_a_co2_airing_that_also_cools_stays_open_for_the_temperature_goal(hass, freezer) -> None:
    d, actions = await _airing(hass, freezer, thermostat_target=21.5)  # 22.1 °C is above target + 0.5
    assert all(action != "Close" for _co2, action, _close in actions), actions
    assert "Cooling still works" in d.room("kueche")["reason"] or "Kühlen wirkt weiter" in d.room("kueche")["reason"]
