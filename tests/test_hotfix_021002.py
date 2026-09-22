from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "freshairiq"
COORD = (COMP / "coordinator.py").read_text(encoding="utf-8")
JS = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")


def test_monitor_only_rooms_keep_real_sensor_values_without_entering_calculations():
    assert '"monitor_only": True' in COORD
    assert '"sensor_data_configured": sensor_configured' in COORD
    assert '"sensor_data_available": monitor_valid' in COORD
    assert '"temperature": round(float(monitor_t), 2) if monitor_valid else None' in COORD
    assert '"humidity": round(float(monitor_rh), 2) if monitor_valid else None' in COORD
    assert '"absolute_humidity": round(float(monitor_ah), 2)' in COORD
    assert '"calculation_enabled": False' in COORD
    assert 'continue' in COORD


def test_monitor_only_room_detail_does_not_render_fake_forecast_or_learning_cards():
    assert 'if (r.calculation_enabled === false)' in JS
    assert 'Sensorwerte verfügbar' in JS
    assert 'Der Raum ist bewusst von Empfehlungen, Prognosen, Hausbilanz und Lernen ausgeschlossen.' in JS
    assert 'Keine Klimasensoren konfiguriert' in JS
    assert 'Sensoren aktuell nicht verfügbar' in JS
    assert 'RAUM-MONITORING' in JS


def test_basics_icon_uses_broadly_supported_mdi_icon():
    assert '["group_basics","mdi:home-outline","Grundlagen"' in JS
    assert '["group_basics","mdi:home-cog","Grundlagen"' not in JS


def test_resident_profile_is_prominently_exposed():
    assert 'resident-profile-spotlight' in JS
    assert 'PERSÖNLICHES FRESHAIRIQ PROFIL' in JS
    assert 'Dein Bewohnerprofil' in JS
    assert 'resident-feature-badge' in JS
    assert 'PERSÖNLICHES IQ-PROFIL' in JS


def test_release_version_021002_everywhere():
    assert 'VERSION = "0.25.0.47"' in (COMP / "const.py").read_text(encoding="utf-8")
    assert '"version": "0.25.0.47"' in (COMP / "manifest.json").read_text(encoding="utf-8")
    assert 'const FAIQ_VERSION = "0.25.0.47";' in JS
    assert 'Current release: 0.25.0.47' in (ROOT / "README.md").read_text(encoding="utf-8")
