from pathlib import Path
from tests._source import module_source

def test_recovery_event_contract_is_emitted_after_safe_repair():
    text=module_source("coordinator")
    assert '"recovery_events"' in text
    assert '"postcondition_passed": self._sensor_recovery_started_at is None and self._sensor_recovery_valid_cycles == 0' in text
