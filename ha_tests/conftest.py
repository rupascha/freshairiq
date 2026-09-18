"""Fixtures for FreshAirIQ tests executed against a real Home Assistant runtime."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load FreshAirIQ from custom_components."""
    yield
