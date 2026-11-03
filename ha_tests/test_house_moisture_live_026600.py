"""0.26.6.0 (order 9): the house map's "removable now" has the very basis of the FreshAirIQ dashboard card.

Both cards take the value from the live channel's ``potential_total_ml`` (while airing ``live_balance_ml``) and the
time from ``recommended_duration_min`` / ``remaining_duration_min`` – through one shared function in the card
(``removableNow``). This checks that the live channel carries exactly the coordinator's values for that basis.
Real Home Assistant, websocket subscription.
"""
from __future__ import annotations

from ha_tests.test_recorder_load_026503 import _entry, _set_sources, _setup

KEYS = ("potential_total_ml", "live_balance_ml", "recommended_duration_min", "remaining_duration_min", "prognosis_confidence")


async def test_the_live_channel_carries_the_basis_of_removable_now(hass, hass_ws_client) -> None:
    _set_sources(hass, "wohnzimmer")
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "freshairiq/dashboard/subscribe"})
    assert (await client.receive_json())["success"] is True
    event = (await client.receive_json())["event"]
    assert {k: event[k] for k in KEYS} == {k: coordinator.data[k] for k in KEYS}
    assert "theoretical_potential_total_ml" not in event       # no second, differing "removable" value
