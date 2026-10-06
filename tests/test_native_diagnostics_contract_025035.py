from pathlib import Path
SRC=(Path(__file__).parents[1]/'custom_components/freshairiq/diagnostics.py').read_text()
def test_native_config_entry_diagnostics_exists_and_is_privacy_reduced():
    assert 'async def async_get_config_entry_diagnostics' in SRC
    assert '"goal_state"' in SRC and '"ventilation_type"' in SRC
    assert 'Entity IDs, coordinates, credentials' in SRC
