"""Node-RED feedback (2026-10-17): ``freshairiq_room_action`` toggled between
"Continue ventilating" and "Close" for the same room every 30 seconds while
the expected return hovered around the close threshold.

Real coordinator, real bus events: with the outdoor humidity jittering around
the threshold the room publishes one close and keeps it; a clearly better
return releases it, and closing the window ends the session.
"""
from __future__ import annotations

from custom_components.freshairiq.automation_events import AutomationEventEmitter
from ha_tests.test_cov_coordinator_b import HUM, _cleanup_coordinators, _data, _make  # noqa: F401


def _schlaf(events) -> list[str]:
    return [p["action"] for name, p in events if name == "freshairiq_room_action" and p["room_key"] == "schlaf"]


async def test_jitter_around_the_threshold_fires_one_close(hass, freezer) -> None:
    events: list = []
    emitter = AutomationEventEmitter(lambda name, payload: events.append((name, payload)), "entry")
    d = await _make(hass, freezer, data=_data(), initial={"sensor.schlaf_h": (64.0, HUM)})
    await d.step(60, binary_sensor__schlaf_fenster="on")
    emitter.process(d.data)
    actions = []
    for i in range(30):
        # the expected 5-minute return alternates between ~20 ml and ~26 ml (threshold 25 ml)
        await d.step(30, sensor__aussen_h=(85.0 if i % 2 else 74.0, HUM))
        emitter.process(d.data)
        actions.append(d.room("schlaf")["action"])
    first_close = actions.index("Close")
    assert set(actions[first_close:]) == {"Close"}
    assert d.mem("schlaf")["close_notified"] is True
    fired = _schlaf(events)
    assert fired == ["close"]  # previously: close / continue_ventilating every cycle

    # clearly drier outdoor air: the close is released once
    await d.step(30, sensor__aussen_h=(55.0, HUM))
    assert d.room("schlaf")["action"] == "Continue ventilating"
    assert d.mem("schlaf")["close_notified"] is False

    # closing the window ends the session and clears the memory
    await d.step(30, binary_sensor__schlaf_fenster="off")
    await d.finish()
    assert d.mem("schlaf")["session_active"] is False
    assert d.mem("schlaf")["close_notified"] is False
