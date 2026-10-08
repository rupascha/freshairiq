"""0.26.4.3: Devices & services is the only place where FreshAirIQ is configured.

The dashboard settings centre (room/resident/level editors, threshold editor,
consent buttons) and its write API were removed so that there is exactly one
settings surface and no second code path that can change the ConfigEntry.
"""
from pathlib import Path

COMP = Path(__file__).resolve().parents[1] / "custom_components/freshairiq"
CARD = (COMP / "frontend/freshairiq-card.js").read_text(encoding="utf-8")


def test_card_never_reads_or_writes_settings():
    assert "freshairiq/settings/" not in CARD
    for gone in ("_settingsPost", "_loadSettings", "_settingsPanel", "_settingsRoomEditor", "_residentProfilesEditor", "threshold-apply", 'data-info="settings"'):
        assert gone not in CARD, gone


def test_no_settings_write_endpoint_is_registered():
    assert not (COMP / "settings_api.py").exists()
    init = (COMP / "__init__.py").read_text(encoding="utf-8")
    assert "FreshAirIQSettingsView" not in init
    assert "hass.http.register_view(FreshAirIQFeedbackView())" in init
    feedback = (COMP / "feedback_api.py").read_text(encoding="utf-8")
    assert "async_update_entry" not in feedback and "def post(" in feedback


def test_consent_hint_points_to_devices_and_services():
    assert 'data-consent-open' in CARD and 'data-consent-later' in CARD
    assert '"/config/integrations/integration/freshairiq"' in CARD
    assert 'data-consent="granted"' not in CARD


def test_support_and_threshold_are_read_only_and_name_the_settings_place():
    assert 'String(((st && st.diagnostics_upload) || {}).configured_reporting_mode || "daily")' in CARD
    assert "Ändern kannst du die Schwelle unter Einstellungen → Geräte & Dienste → FreshAirIQ → Konfigurieren." in CARD
