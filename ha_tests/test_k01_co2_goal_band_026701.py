"""K01 (0.26.7.1): CO2 goal and CO2 hold band agree in the real coordinator, down to the entity payload.

Warning 1000 ppm, configured release 750 ppm. Once the kitchen airing for CO2 started, the room keeps airing down to
750 ppm; the published CO2 goal must then be open with target 750 ppm – not "reached, target 1000, ETA 0".
"""
from __future__ import annotations

from custom_components.freshairiq.dashboard_transport import stable_room_payload
from ha_tests.test_cov_coordinator_b import CO2, HUM, OPTIONS, _cleanup_coordinators, _make  # noqa: F401


def _goal(room):
    return next(g for g in room["goal_state"]["goals"] if g["id"] == "co2")


async def test_co2_goal_follows_the_hold_band_from_coordinator_to_entity_payload(hass, freezer) -> None:
    climate = ("heat", {"temperature": 23.0, "current_temperature": 22.1, "hvac_action": "heating"})
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400, "co2_release": 750},
                    initial={"climate.kueche": climate})
    for _ in range(3):
        await d.step(60)
    kitchen = d.room("kueche")
    assert kitchen["action"] == "Ventilate" and d.mem("kueche")["co2_lead_latched"] is True
    assert _goal(kitchen)["reached"] is False and _goal(kitchen)["target"] == 750.0
    await d.step(60, binary_sensor__kueche_fenster="on")
    seen = []
    for i, co2 in enumerate((1100, 1020, 960, 900, 850, 800, 760, 751)):
        await d.step(60, sensor__kueche_co2=(co2, CO2), sensor__kueche_h=(round(61 - 0.2 * (i + 1), 1), HUM))
        room = d.room("kueche")
        goal = _goal(room)
        seen.append((co2, room["action"], goal["reached"], goal["target"]))
        assert d.mem("kueche")["co2_lead_latched"] is True
        assert goal["reached"] is False and goal["target"] == 750.0 and goal["achievable_now"] is True, seen
        assert goal["eta_min"] != 0.0, seen
        assert room["action"] != "Close", seen
        # what the room action entity publishes for dashboards carries the same goal line
        payload_goal = next(g for g in stable_room_payload(room)["goal_state"]["goals"] if g["id"] == "co2")
        assert (payload_goal["reached"], payload_goal["target"]) == (False, 750.0)
    await d.step(60, sensor__kueche_co2=(740, CO2))
    goal = _goal(d.room("kueche"))
    assert d.mem("kueche")["co2_lead_latched"] is False
    assert goal["reached"] is True and goal["target"] == 1000.0 and goal["latched"] is False
