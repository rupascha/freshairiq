"""0.26.5.4: a closed window is not told to keep ventilating while its final measurement runs.

After the contact closes, the session lives on for a short final measurement
(``session_finalization_pending``). The room and the house recommendation used
the session flag as "still aired" and showed "Continue ventilating" (or
"Close") for an already closed window for one more cycle.
"""
from __future__ import annotations

from ha_tests.test_cov_coordinator_b import CO2, OPTIONS, _cleanup_coordinators, _make  # noqa: F401


async def test_closed_kitchen_in_its_final_measurement_is_no_longer_aired(hass, freezer) -> None:
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400})
    for _ in range(3):
        await d.step(60)
    await d.step(60, binary_sensor__kueche_fenster="on")
    for co2 in (1100, 1060, 1030):
        await d.step(60, sensor__kueche_co2=(co2, CO2))
    assert d.room("kueche")["action"] == "Continue ventilating"
    await d.step(60, binary_sensor__kueche_fenster="off")
    await d.step(5)  # the 3 s close confirmation has passed, the final measurement waits for the sensors
    kitchen = d.room("kueche")
    assert kitchen["active"] is True and kitchen["open"] is False and kitchen["session_finalization_pending"] is True
    assert kitchen["action"] not in {"Continue ventilating", "Close", "Ventilate"}, kitchen["action"]
    assert kitchen["recently_ventilated"] is True and kitchen["minutes_since_last_ventilation"] is not None
    house = d.coordinator.data["intelligent_recommendation"]
    assert not (house["kind"] in {"continue", "close"} and "kueche" in (house.get("room_keys") or [])), house
