"""Node-RED feedback (2026-10-17): ``freshairiq_room_action`` toggled between
"Continue ventilating" and "Close" for the same room every 30 seconds while
the expected return hovered around the close threshold.

Real coordinator, real bus events: with the outdoor humidity jittering around
the threshold the room publishes one close and keeps it; a clearly better
return releases it, and closing the window ends the session.
"""
from __future__ import annotations

from custom_components.freshairiq.automation_events import AutomationEventEmitter
from ha_tests.test_cov_coordinator_b import HUM, TEMP, _cleanup_coordinators, _data, _make  # noqa: F401


def _schlaf(events) -> list[str]:
    return [p["action"] for name, p in events if name == "freshairiq_room_action" and p["room_key"] == "schlaf"]


async def test_jitter_around_the_threshold_fires_one_close(hass, freezer) -> None:
    events: list = []
    emitter = AutomationEventEmitter(lambda name, payload: events.append((name, payload)), "entry")
    # Testvermerk 0.26.7.0 (F11): a small return no longer closes while the outdoor air is drier (it was ~3–4 g/m³
    # drier here). The jitter now hovers around the close criterion itself: outdoor air at 16 °C alternating between
    # ~0.26 and ~0.47 g/m³ drier than the room (close at ≤ 0.4, release only at ≥ 0.7 with fresh readings).
    d = await _make(hass, freezer, data=_data(), initial={"sensor.schlaf_h": (64.0, HUM), "sensor.aussen_t": (16.0, TEMP)})
    await d.step(60, binary_sensor__schlaf_fenster="on")
    emitter.process(d.data)
    actions = []
    for i in range(30):
        await d.step(30, sensor__aussen_h=(76.0 if i % 2 else 74.5, HUM))
        emitter.process(d.data)
        actions.append(d.room("schlaf")["action"])
    first_close = actions.index("Close")
    assert set(actions[first_close:]) == {"Close"}
    assert d.mem("schlaf")["close_notified"] is True
    fired = _schlaf(events)
    assert fired == ["close"]  # previously: close / continue_ventilating every cycle

    # clearly drier outdoor air: the close is released once
    # Testvermerk 0.26.7.0 (F11): a stored close is lifted only by fresh room readings that prove drying again
    await d.step(30, sensor__aussen_h=(55.0, HUM), sensor__schlaf_h=(63.9, HUM))
    await d.step(30, sensor__schlaf_h=(63.8, HUM))
    assert d.room("schlaf")["action"] == "Continue ventilating"
    assert d.mem("schlaf")["close_notified"] is False

    # closing the window ends the session and clears the memory
    await d.step(30, binary_sensor__schlaf_fenster="off")
    await d.finish()
    assert d.mem("schlaf")["session_active"] is False
    assert d.mem("schlaf")["close_notified"] is False
