from tests.release_version import CURRENT_RELEASE_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = (ROOT / "custom_components/freshairiq/feedback_api.py").read_text(encoding="utf-8")
COORDINATOR = (ROOT / "custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
CONFIG_FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")


# test_020307_runtime_settings_use_lightweight_refresh: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services).


# test_020307_only_structural_dashboard_room_changes_keep_reload: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services).


def test_020307_coordinator_can_rebuild_source_listeners_without_unload():
    assert "def _clear_runtime_listeners(self) -> None:" in COORDINATOR
    assert "async def async_rebuild_listeners(self, *, invalidate_weather_cache: bool = False) -> None:" in COORDINATOR
    assert "self._hourly_forecast_cache = []" in COORDINATOR
    assert "self._hourly_forecast_fetched_at = None" in COORDINATOR
    assert "await self.async_start_listeners()" in COORDINATOR
    assert "await self.store.async_save()" in COORDINATOR  # still only shutdown/reload path


def test_020307_native_options_flow_avoids_reload_for_non_structural_changes():
    assert 'old_room_keys = {str(room.get("key")) for room in old_data.get(CONF_ROOMS, [])}' in CONFIG_FLOW
    assert 'new_room_keys = {str(room.get("key")) for room in new_data.get(CONF_ROOMS, [])}' in CONFIG_FLOW
    assert "structural_change = old_room_keys != new_room_keys" in CONFIG_FLOW
    assert "if structural_change:" in CONFIG_FLOW
    assert "self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)" in CONFIG_FLOW
    assert "await coordinator.async_rebuild_listeners(" in CONFIG_FLOW
    assert "invalidate_weather_cache=invalidate_weather_cache" in CONFIG_FLOW
    assert "await coordinator.async_request_refresh()" in CONFIG_FLOW



def test_020307_forecast_and_profile_controls_publish_immediately_then_refresh_background():
    number = (ROOT / "custom_components/freshairiq/number.py").read_text(encoding="utf-8")
    select = (ROOT / "custom_components/freshairiq/select.py").read_text(encoding="utf-8")
    assert "self.async_write_ha_state()" in number
    assert "self.hass.async_create_task(self.coordinator.async_request_refresh())" in number
    assert "await self.coordinator.async_request_refresh()" not in number
    assert "self.async_write_ha_state()" in select
    assert "self.hass.async_create_task(self.coordinator.async_request_refresh())" in select
    assert "await self.coordinator.async_request_refresh()" not in select


# test_020307_settings_http_ack_does_not_wait_for_full_recalculation: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services).

def test_020307_version_is_consistent():
    assert f'VERSION = "{CURRENT_RELEASE_VERSION}"' in (ROOT / "custom_components/freshairiq/const.py").read_text(encoding="utf-8")
    assert f'"version": "{CURRENT_RELEASE_VERSION}"' in (ROOT / "custom_components/freshairiq/manifest.json").read_text(encoding="utf-8")
    assert f'const FAIQ_VERSION = "{CURRENT_RELEASE_VERSION}";' in (ROOT / "custom_components/freshairiq/frontend/freshairiq-card.js").read_text(encoding="utf-8")
