from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTIFICATIONS = (ROOT / "custom_components/freshairiq/notifications.py").read_text(encoding="utf-8")
CONFIG_FLOW = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
SETTINGS_API = (ROOT / "custom_components/freshairiq/feedback_api.py").read_text(encoding="utf-8")

def test_backend_discovery_covers_state_registry_and_persisted_targets():
    assert "def _available_notification_targets" in NOTIFICATIONS
    assert 'startswith("notify.")' in NOTIFICATIONS
    assert "entity_registry as er" in NOTIFICATIONS
    assert 'value.startswith("entity:notify.")' in NOTIFICATIONS

def test_native_options_include_modern_notify_entities():
    assert '_available_notification_targets(hass, current.get("notification_targets", []))' in CONFIG_FLOW
    assert '"value": f"entity:{entity_id}"' in CONFIG_FLOW
    assert 'notify.send_message' in CONFIG_FLOW

# test_dashboard_and_native_flow_share_same_backend_discovery: retired — dashboard settings and their write API removed in 0.26.4.3 (single settings surface: Devices & services).
