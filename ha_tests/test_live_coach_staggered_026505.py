"""0.26.5.5 (F06, GitHub #24) in a real Home Assistant: a window opened while another room's
airing ends never reads "Close" before its own close is released.

The hallway is aired for six minutes and closed; the bathroom window was opened a few
minutes later. Every 10 seconds the bathroom's published action is checked against its
own close release – through the house decision, the live coach and the presentation.
This is the invariant over the whole chain; the exact #24 state (the closed room still
``active`` during a longer final measurement) is reproduced in
tests/test_live_coach_staggered_026505.py, where the old code fails.
"""
from __future__ import annotations

from ha_tests.test_door_delay_cooling_026504 import NOTIFY, _rooms, _settled


async def test_bathroom_never_closes_before_its_own_release(hass, freezer) -> None:
    rooms = _rooms(flur_delay=0)
    rooms[0]["contact_delays"]["binary_sensor.bad_tuer"] = 0
    options = {**NOTIFY, "min_duration_min": 5, "max_duration_min": 30}
    d = await _settled(hass, freezer, rooms, options=options, initial={"sensor.bad_h": (68.0, {"unit_of_measurement": "%", "device_class": "humidity"}),
                                                                       "sensor.flur_h": (66.0, {"unit_of_measurement": "%", "device_class": "humidity"})})
    await d.step(30, binary_sensor__flur_tuer="on")
    for _ in range(9):
        await d.step(30)
    await d.step(30, binary_sensor__bad_tuer="on")      # bathroom opened while the hallway airing runs
    await d.step(30)
    seen = []
    await d.step(2, binary_sensor__flur_tuer="off")       # hallway closed: its final measurement starts
    for _ in range(18):
        await d.step(10)
        bad = d.room("badezimmer")
        seen.append((bad["action"], bool(bad.get("close_recommended")), bad.get("session_elapsed_min")))
        if bad["action"] == "Close" and float(bad.get("session_elapsed_min") or 0) < 5:
            assert bad.get("close_recommended") or float(bad.get("delta_g_m3") or 0) < 0, seen
    assert d.mem("badezimmer")["session_active"] is True
