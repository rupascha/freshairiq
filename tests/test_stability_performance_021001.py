from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = (ROOT / 'custom_components/freshairiq/coordinator.py').read_text(encoding='utf-8')
CONFIG_FLOW = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text(encoding='utf-8')
STORAGE = (ROOT / 'custom_components/freshairiq/storage.py').read_text(encoding='utf-8')
DIAGNOSTICS = (ROOT / 'custom_components/freshairiq/diagnostics.py').read_text(encoding='utf-8')
FRONTEND = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text(encoding='utf-8')


def test_structure_only_room_guard_precedes_calculation_pipeline():
    loop = COORDINATOR.split('for idx, cfg in enumerate(rooms_cfg):', 1)[1]
    branch = loop.split('            temperature_entity = cfg.get(CONF_ROOM_TEMPERATURE)', 2)
    assert len(branch) >= 3
    monitor = branch[1]
    assert 'if not include:' in branch[0]
    assert '"calculation_enabled": False' in monitor
    assert '"monitor_only": True' in monitor
    assert 'continue' in monitor
    assert 'cfg[CONF_ROOM_TEMPERATURE]' not in monitor
    assert 'cfg[CONF_ROOM_HUMIDITY]' not in monitor


def test_native_room_flow_allows_structure_rooms_but_validates_active_rooms():
    assert '_optional(CONF_ROOM_TEMPERATURE' in CONFIG_FLOW
    assert '_optional(CONF_ROOM_HUMIDITY' in CONFIG_FLOW
    assert 'if include and not has_temperature and not has_humidity and not contacts:' in CONFIG_FLOW
    assert 'include = False' in CONFIG_FLOW
    assert 'if include and not has_temperature:' in CONFIG_FLOW
    assert 'if include and not has_humidity:' in CONFIG_FLOW
    assert 'if include and not contacts:' in CONFIG_FLOW


def test_weather_failure_preserves_cache_and_retries_soon():
    assert 'fetched_forecast = await async_hourly_forecast' in COORDINATOR
    assert 'if fetched_forecast:' in COORDINATOR
    assert 'self._hourly_forecast_cache = fetched_forecast' in COORDINATOR
    assert 'now - timedelta(seconds=540)' in COORDINATOR


def test_event_bursts_and_water_history_are_rate_limited():
    assert 'async_call_later(self.hass, 0.12, _coalesced_refresh)' in COORDINATOR
    assert 'if self._refresh_coalesce_unsub is None:' in COORDINATOR
    assert 'if (when - last).total_seconds() < 60:' in STORAGE
    assert 'return False' in STORAGE


def test_diagnostics_and_webview_compatibility_hardening():
    assert '_legacy_compaction_mtime_ns' in DIAGNOSTICS
    assert 'st_mtime_ns' in DIAGNOSTICS
    assert '-webkit-backdrop-filter:blur(8px)' in FRONTEND
    assert '-webkit-backdrop-filter:blur(12px)' in FRONTEND


def test_structure_room_ui_never_invents_zero_climate_values():
    assert 'Keine Klimasensoren erforderlich' in FRONTEND
    assert 'ohne erfundene Klimawerte' in FRONTEND
    assert 'structureOnly ? ""' in FRONTEND
