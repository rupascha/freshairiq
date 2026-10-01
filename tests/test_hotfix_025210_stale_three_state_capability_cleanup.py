from pathlib import Path
from types import SimpleNamespace

from custom_components.freshairiq.opening_state import opening_contact_profile


class _States:
    def __init__(self, rows): self._rows = rows
    def get(self, entity_id): return self._rows.get(entity_id)


class _Hass:
    def __init__(self, rows): self.states = _States(rows)


def _state(value, **attrs):
    return SimpleNamespace(state=value, attributes=attrs)


def test_removed_three_state_contact_cannot_promote_replacement_binary_contact():
    hass = _Hass({"binary_sensor.window": _state("on")})
    configured = ["binary_sensor.window"]
    remembered = {"sensor.old_handle"} & set(configured)
    modes, proven = opening_contact_profile(hass, configured, remembered)
    assert modes == {"binary_sensor.window": "open"}
    assert proven == set()


def test_replacement_explicit_three_state_contact_is_detected_without_old_capability():
    hass = _Hass({"sensor.new_handle": _state("closed", options=["closed", "open", "tilted"])})
    configured = ["sensor.new_handle"]
    remembered = {"sensor.old_handle"} & set(configured)
    modes, proven = opening_contact_profile(hass, configured, remembered)
    assert modes == {"sensor.new_handle": "closed"}
    assert proven == {"sensor.new_handle"}


def test_coordinator_prunes_all_contact_scoped_runtime_memory_and_quarantines_mid_session_change():
    text = Path("custom_components/freshairiq/coordinator.py").read_text(encoding="utf-8")
    assert 'remembered_three_state = remembered_all & configured_contacts' in text
    assert 'if str(k) in configured_contacts' in text
    assert 'session_passage_contacts = [str(x) for x in session_passage_raw if str(x) in configured_contacts]' in text
    assert 'mem["session_opening_mode_mixed"] = True' in text
    assert 'mem["session_learning_quarantine_code"] = "FAIQ-OPENING-3STATE-004"' in text


def test_binary_sensor_can_never_become_explicit_three_state_from_remembered_capability():
    hass = _Hass({"binary_sensor.window": _state("on", options=["closed", "open", "tilted"])})
    modes, proven = opening_contact_profile(hass, ["binary_sensor.window"], set())
    assert modes["binary_sensor.window"] == "open"
    assert proven == set()
