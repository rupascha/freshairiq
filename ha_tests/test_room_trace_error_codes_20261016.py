"""F12 (2026-10-16): a rejected room creation records *why*, without user input."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.freshairiq.room_creation_trace import validation_error_codes
from ha_tests.test_cov_options_flow import _entry, _open, _room_input, _submit


def test_only_fixed_error_codes_pass() -> None:
    errors = {"base": "room_volume_required", "name": "Küche Müller", "x": "contact_reference_pair_required"}
    assert validation_error_codes(errors) == ["contact_reference_pair_required", "room_volume_required"]
    assert validation_error_codes({}) == []
    assert validation_error_codes(None) == []


async def test_rejected_room_in_options_flow_traces_error_code(hass) -> None:
    events: list[dict] = []

    async def _record(event):
        events.append(event)
        return True

    entry = _entry()
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(diagnostics=SimpleNamespace(async_record_room_creation_trace=_record))
    result = await _open(hass, entry, "home_setup", "rooms", "add_room")
    result = await _submit(hass, result, _room_input("Küche", "kueche", volume=None))
    assert result["errors"] == {"base": "room_volume_required"}
    await hass.async_block_till_done()
    rejected = [e for e in events if e["stage"] == "validation_failed"]
    assert len(rejected) == 1
    assert rejected[0]["validation_error_keys"] == ["base"]
    assert rejected[0]["validation_error_codes"] == ["room_volume_required"]
    # never the room name or entity ids
    assert "Küche" not in repr(rejected[0]) and "sensor." not in repr(rejected[0])
