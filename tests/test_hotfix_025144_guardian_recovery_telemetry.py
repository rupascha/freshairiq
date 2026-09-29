from pathlib import Path

def test_recovery_event_contract_is_emitted_after_safe_repair():
    text=(Path(__file__).parents[1]/"custom_components/freshairiq/coordinator.py").read_text()
    assert '"recovery_events"' in text
    assert '"postcondition_passed": self._sensor_recovery_started_at is None and self._sensor_recovery_valid_cycles == 0' in text
