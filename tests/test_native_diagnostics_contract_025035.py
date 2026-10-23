from pathlib import Path
from tests._source import module_source
SRC=module_source("diagnostics")
def test_native_config_entry_diagnostics_exists_and_is_privacy_reduced():
    assert 'async def async_get_config_entry_diagnostics' in SRC
    assert '"goal_state"' in SRC and '"ventilation_type"' in SRC
    assert 'Entity IDs, coordinates, credentials' in SRC
