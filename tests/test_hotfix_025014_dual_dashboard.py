from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / 'custom_components/freshairiq/frontend/freshairiq-card.js'


def test_dual_dashboard_variants_share_backend_and_keep_classic_renderer():
    text = CARD.read_text(encoding='utf-8')
    assert 'dashboard_variant: ["classic", "iq"].includes' in text
    assert 'dashboardVariant === "classic" ? this._intelligentPanel(st, rooms) : this._compactAIPanel(st, rooms)' in text
    assert 'dashboardVariant === "classic" ? classicTopBar : iqTopBar' in text
    assert 'INTELLIGENT HOME CLIMATE' in text
    assert 'DEIN KLIMA · VON FRESHAIRIQ BEWERTET' in text


def test_dashboard_variant_is_selectable_and_bilingual():
    text = CARD.read_text(encoding='utf-8')
    for token in (
        'id="dashboard-variant"',
        'DASHBOARD-DESIGN', 'DASHBOARD DESIGN',
        'Darstellung', 'Dashboard style',
        'Klassisch', 'Classic',
        'Wähle zwischen dem klassischen FreshAirIQ-Dashboard',
        'Choose between the classic FreshAirIQ dashboard',
    ):
        assert token in text
    assert 'config-changed' in text


def test_version_is_025014():
    text = CARD.read_text(encoding='utf-8')
    assert 'const FAIQ_VERSION = "0.25.1.6";' in text
