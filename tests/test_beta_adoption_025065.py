from pathlib import Path
from tests._source import module_source

ROOT = Path(__file__).resolve().parents[1]


def test_beta_funnel_is_derived_inside_diagnostics_only():
    diagnostics = module_source("diagnostics")
    assert '"beta_funnel": beta_funnel' in diagnostics
    assert '"first_valid_analysis_at"' in diagnostics
    assert '"first_recommendation_at"' in diagnostics
    assert '"first_followed_recommendation_at"' in diagnostics
    assert '"returning_user"' in diagnostics


def test_beta_release_does_not_change_upload_schema():
    transport = module_source("diagnostic_transport")
    assert "UPLOAD_SCHEMA_VERSION = 2" in transport
