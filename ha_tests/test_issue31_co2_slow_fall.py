"""#31: a running CO2 airing gives up once CO2 levels off above the release level (real coordinator)."""
from __future__ import annotations

from ha_tests.test_cov_coordinator_b import CO2, HUM, OPTIONS, TEMP, _cleanup_coordinators, _make  # noqa: F401


async def test_co2_levelling_off_releases_the_hold_once_and_claims_no_goal(hass, freezer) -> None:
    # the kitchen is dry enough (50 % <= target 65 %) and not too warm: only CO2 keeps the airing open; the default room
    # strategy "close once the goals are reached" is in effect
    d = await _make(hass, freezer, options={**OPTIONS, "co2_warn": 1000, "co2_critical": 1400, "co2_release": 600, "min_duration_min": 3, "target_rh": 65},
                    initial={"sensor.kueche_h": (50.0, HUM), "sensor.kueche_t": (21.0, TEMP)})
    for _ in range(3):
        await d.step(60)
    await d.step(60, binary_sensor__kueche_fenster="on")

    async def report(ppm: float, advance: float = 60) -> None:
        await d.step(advance, sensor__kueche_co2=(ppm, CO2), sensor__kueche_h=(50.0, HUM), sensor__kueche_t=(21.0, TEMP))  # fresh readings too

    samples = d.coordinator._co2_samples["kueche"]
    await report(1100)
    assert d.mem("kueche")["co2_lead_latched"] is True
    count = len(samples)
    for _ in range(3):  # refreshes without a new sensor report add no sample
        await d.step(20)
    assert len(samples) == count
    for ppm in (900, 750, 700, 698):  # a clear fall: the airing goes on
        await report(ppm)
        assert d.mem("kueche")["co2_lead_latched"] is True and not d.mem("kueche").get("session_co2_given_up")
    assert d.coordinator._co2_steepest["kueche"] < -20  # the fast fall was seen
    for ppm in (697, 696):  # levelled off 97 ppm above the release level: the condition must hold for 120 s first
        await report(ppm)
        assert d.mem("kueche")["co2_lead_latched"] is True and not d.mem("kueche").get("session_co2_given_up")
    await report(695)  # held across three reports
    mem = d.mem("kueche")
    assert mem["co2_lead_latched"] is False and mem["session_co2_given_up"] is True
    co2_goal = next(g for g in d.room("kueche")["goal_state"]["goals"] if g["id"] == "co2")
    assert not co2_goal["reached"] and co2_goal["target"] == 600  # the goal row stays open, aimed at the release level
    assert d.room("kueche")["action"] == "Close" and d.room("kueche")["close_kind"] == "air_no_longer_helps"  # not "goals reached"
    await report(650)  # a fast fall afterwards does not re-arm the hold below the warning threshold
    assert d.mem("kueche")["co2_lead_latched"] is False

    await d.step(60, binary_sensor__kueche_fenster="off")
    await d.finish()
    assert d.mem("kueche")["session_active"] is False and not d.mem("kueche").get("session_co2_given_up")
    await d.step(60, binary_sensor__kueche_fenster="on")  # a new airing starts without the old samples
    assert [ppm for _t, ppm in samples] == [650.0]
    assert "kueche" not in d.coordinator._co2_steepest and "kueche" not in d.coordinator._co2_since  # cleared with the samples
