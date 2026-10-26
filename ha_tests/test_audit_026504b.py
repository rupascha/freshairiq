"""0.26.5.4: preventive audit of the 0.26.5.4 artefact, in a real Home Assistant.

P1-07  a humidity sensor that stays silent during an airing makes no plateau; a
       sensor that keeps reporting the same value does.
P1-04  the CO2 sensor of a CO2 airing becomes unavailable: the airing is not taken
       for "CO2 is down", the room says that the sensor reports no value.
"""
from __future__ import annotations

from custom_components.freshairiq.humidity_plateau import humidity_plateau

from ha_tests.test_cov_coordinator_b import CO2, HUM, OPTIONS, _cleanup_coordinators, _make  # noqa: F401


def _plateau_now(mem) -> bool:
    window = mem["session_humidity_window"]
    last = window[-1]
    return humidity_plateau(window, last["t"], last["rh"], last["ah"], mem.get("session_humidity_reports"))


async def _airing(hass, freezer, *, reports: bool):
    d = await _make(hass, freezer, options=OPTIONS)
    await d.step(60)
    await d.step(60, binary_sensor__schlaf_fenster="on")
    for _ in range(18):
        await d.step(60, **({"sensor__schlaf_h": (d.hass.states.get("sensor.schlaf_h").state, HUM)} if reports else {}))
    return d


async def test_a_silent_humidity_sensor_makes_no_plateau(hass, freezer) -> None:
    d = await _airing(hass, freezer, reports=False)
    mem = d.mem("schlaf")
    assert mem["session_active"] is True and len({s["n"] for s in mem["session_humidity_window"]}) == 1
    assert _plateau_now(mem) is False


async def test_a_sensor_reporting_the_same_value_makes_a_plateau(hass, freezer) -> None:
    d = await _airing(hass, freezer, reports=True)
    mem = d.mem("schlaf")
    assert mem["session_humidity_reports"] >= 15
    assert _plateau_now(mem) is True


async def test_an_unavailable_co2_sensor_is_no_co2_reached(hass, freezer) -> None:
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400})
    for _ in range(3):
        await d.step(60)
    assert d.room("kueche")["action"] == "Ventilate"
    await d.step(60, binary_sensor__kueche_fenster="on")
    for i, co2 in enumerate((1150, 1120)):
        await d.step(60, sensor__kueche_co2=(co2, CO2), sensor__kueche_h=(round(60.8 - 0.2 * i, 1), HUM))
    assert d.mem("kueche")["session_co2_only"] is True
    for i in range(6):  # fresh climate readings: the close decision is ready, past the minimum duration
        await d.step(60, sensor__kueche_co2=("unavailable", CO2), sensor__kueche_h=(round(60.4 - 0.1 * i, 1), HUM))
    kitchen = d.room("kueche")
    assert kitchen["close_decision_ready"] is True and kitchen["session_elapsed_min"] >= 3
    assert kitchen["co2_sensor_missing"] is True and kitchen["action"] == "Continue ventilating", kitchen["action"]
    assert "The CO₂ sensor reports no value; CO₂ is not assessed, the airing follows its planned duration" in kitchen["recommendation_reasons"]
