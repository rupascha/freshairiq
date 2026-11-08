"""0.26.7.0 UI hotfix: the dashboard live channel also carries the outdoor absolute humidity (additive).

The house map's weather display and weather window offer "absolute humidity"; without an own weather entity they show
FreshAirIQ's own value – exactly what the decision computed (``coordinator_decision``: ``model.absolute_humidity`` of the
outdoor temperature and humidity), not a second calculation in the browser.
"""
from __future__ import annotations

from custom_components.freshairiq.model import absolute_humidity
from ha_tests.test_cov_setup_and_platforms import _entry, _set_sources, _setup


async def test_live_payload_carries_the_outdoor_absolute_humidity(hass, hass_ws_client) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    data = entry.runtime_data.data
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "freshairiq/dashboard/subscribe"})
    assert (await client.receive_json())["success"] is True
    event = (await client.receive_json())["event"]
    assert "outdoor_absolute_humidity" in event and event["outdoor_absolute_humidity"] == data.get("outdoor_absolute_humidity")
    t, rh = data.get("outdoor_temperature"), data.get("outdoor_humidity")
    assert t is not None and rh is not None   # the test entry has outdoor sensors
    assert event["outdoor_absolute_humidity"] == round(absolute_humidity(t, rh), 3) > 0
    # still everything that was there before (additive)
    for key in ("outdoor_temperature", "outdoor_humidity", "wind_bearing", "wind_speed", "weather_now"):
        assert key in event
