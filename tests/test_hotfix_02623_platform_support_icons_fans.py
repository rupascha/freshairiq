from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js').read_text()
FLOW = (ROOT / 'custom_components/freshairiq/config_flow.py').read_text()
COORD = (ROOT / 'custom_components/freshairiq/coordinator.py').read_text()
CONST = (ROOT / 'custom_components/freshairiq/const.py').read_text()

def test_support_upload_uses_embedded_ui_not_browser_origin_prompt():
    block = CARD[CARD.index('async _sendDiagnosticsToDeveloper()'):CARD.index('_settingsEntryId()', CARD.index('async _sendDiagnosticsToDeveloper()'))]
    assert 'window.prompt' not in block
    assert 'diagnostics-message' in block
    assert 'FreshAirIQ-Diagnose-Server' in CARD

def test_overlay_surface_is_explicitly_dark_across_host_themes():
    assert '.subdialog{color:#e9f0f4' in CARD
    assert 'background:linear-gradient(145deg,#171f28,#10171e)' in CARD
    assert 'color-scheme:dark' in CARD

def test_room_humidity_chart_has_y_axis_ticks():
    assert 'const ticks = [axisMax, axisMin + span / 2, axisMin]' in CARD
    assert 'field === "humidity_percent" ? "%" : "°C"' in CARD

def test_room_icon_is_configurable_and_propagated():
    assert 'CONF_ROOM_ICON = "icon"' in CONST
    assert 'selector.IconSelector()' in FLOW
    assert '"icon": cfg.get(CONF_ROOM_ICON)' in COORD
    assert 'customIcon.startsWith("mdi:")' in CARD

def test_multiple_mechanical_exhaust_entities_keep_legacy_compatibility():
    assert 'multiple=True' in FLOW[FLOW.index('CONF_ROOM_EXHAUST_FAN'):]
    assert 'isinstance(entity_id, str)' in COORD
    assert 'for current in entity_ids' in COORD

def test_sensor_selectors_filter_known_device_classes():
    for device_class in ('temperature', 'humidity', 'carbon_dioxide', 'pm25', 'illuminance'):
        assert f'device_class="{device_class}"' in FLOW
