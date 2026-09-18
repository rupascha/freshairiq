"""Native Home Assistant exception behaviour for FreshAirIQ entity actions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.freshairiq.button import ResetLearningButton, ResetStatisticsButton
from custom_components.freshairiq.select import FreshAirIQOperatingProfileSelect


@pytest.mark.asyncio
async def test_invalid_operating_profile_is_service_validation_error() -> None:
    coordinator = SimpleNamespace(options={"operating_profile": "comfort"})
    entry = SimpleNamespace(entry_id="entry", options={})
    entity = FreshAirIQOperatingProfileSelect(coordinator, entry)
    with pytest.raises(ServiceValidationError) as err:
        await entity.async_select_option("invalid")
    assert err.value.translation_key == "unsupported_operating_profile"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (entity_cls, method_name, translation_key),
    [
        (ResetLearningButton, "async_reset_learning", "reset_learning_failed"),
        (ResetStatisticsButton, "async_reset_statistics", "reset_statistics_failed"),
    ],
)
async def test_reset_buttons_wrap_storage_failures(entity_cls, method_name, translation_key) -> None:
    failing = AsyncMock(side_effect=OSError("disk error"))
    store = SimpleNamespace(**{method_name: failing})
    coordinator = SimpleNamespace(store=store, async_request_refresh=AsyncMock())
    entry = SimpleNamespace(entry_id="entry")
    entity = entity_cls(coordinator, entry)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_press()
    assert err.value.translation_key == translation_key
