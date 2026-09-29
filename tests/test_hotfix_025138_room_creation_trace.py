from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_025138_trace_is_wired_into_all_room_creation_surfaces():
    config = (ROOT / "custom_components/freshairiq/config_flow.py").read_text(encoding="utf-8")
    settings = (ROOT / "custom_components/freshairiq/settings_api.py").read_text(encoding="utf-8")
    assert 'source="native_subentry"' in config
    assert 'stage="subentry_commit_timeout"' in config
    assert 'stage="subentry_commit_observed"' in config
    assert 'source="options_flow"' in config
    assert 'source="dashboard"' in settings
    assert 'stage="parent_and_subentries_persisted"' in settings
    assert "trace_room_creation_after_reload" in config
    assert "trace_room_creation_after_reload" in settings


def test_025138_trace_privacy_contract_and_export_record_type():
    trace = (ROOT / "custom_components/freshairiq/room_creation_trace.py").read_text(encoding="utf-8")
    diagnostics = (ROOT / "custom_components/freshairiq/diagnostics.py").read_text(encoding="utf-8")
    assert "parent_room_fingerprints" in trace
    assert "room_subentry_fingerprints" in trace
    assert '"record_type": "room_creation_trace"' in diagnostics
    assert '"reason": "room_creation_trace"' in diagnostics
    assert "raw form payloads" in diagnostics


def test_025138_release_notes_remain_as_historical_record():
    assert (ROOT / "docs/releases/RELEASE_NOTES_0.25.1.38.md").is_file()
    assert (ROOT / "custom_components/freshairiq/room_creation_trace.py").is_file()
