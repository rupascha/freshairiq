from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_beta_funnel_is_derived_inside_diagnostics_only():
    diagnostics = (ROOT / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert '"beta_funnel": beta_funnel' in diagnostics
    assert '"first_valid_analysis_at"' in diagnostics
    assert '"first_recommendation_at"' in diagnostics
    assert '"first_followed_recommendation_at"' in diagnostics
    assert '"returning_user"' in diagnostics


def test_beta_release_does_not_change_upload_schema():
    transport = (ROOT / "custom_components/freshairiq/diagnostic_transport.py").read_text(encoding="utf-8")
    assert "UPLOAD_SCHEMA_VERSION = 2" in transport
