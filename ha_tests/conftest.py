"""Fixtures for FreshAirIQ tests executed against a real Home Assistant runtime."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load FreshAirIQ from custom_components."""
    yield


@pytest.fixture(autouse=True)
async def _finish_background_work(request):
    """Let reloads started by a flow finish before Home Assistant stops.

    A successful options/reconfigure flow reloads the entry in the background.
    If the test ends first, Home Assistant stops in the middle of that setup and
    leaves its timers behind, which fails the test intermittently.
    """
    hass = request.getfixturevalue("hass") if "hass" in request.fixturenames else None
    yield
    if hass is not None and hass.is_running:
        await hass.async_block_till_done(wait_background_tasks=True)
