"""0.26.6.0 (7): "Mould & CO₂" in the native options flow offers all four mould risk limits.

The form shows the four fields with the stored values (defaults 60/70/80/90 % for a new setup), saves own
values, rejects limits that do not rise strictly, and an older setup keeps its own "high"/"very high" limits.
Real Home Assistant options flow.
"""
from __future__ import annotations

from homeassistant.data_entry_flow import FlowResultType

from ha_tests.test_cov_options_flow import _entry, _open, _room, _submit

KEYS = ("mould_slight_surface_rh", "mould_elevated_surface_rh", "mould_warn_surface_rh", "mould_critical_surface_rh")
SECTIONS = ("humidity_thresholds", "recommendation_thresholds", "ventilation_timing", "efficiency", "health_limits", "learning")


def _defaults(result) -> dict:
    schema = result["data_schema"].schema
    section = next(value for key, value in schema.items() if str(key) == "health_limits")
    return {str(k): k.default() for k in section.schema.schema if str(k) in KEYS}


def _input(**health) -> dict:
    return {**{name: {} for name in SECTIONS}, "health_limits": health}


async def test_the_form_shows_four_limits_saves_them_and_rejects_a_wrong_order(hass) -> None:
    entry = _entry(rooms=[_room()])
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "model")
    assert result["type"] is FlowResultType.FORM
    assert _defaults(result) == dict(zip(KEYS, (60, 70, 80, 90)))
    result = await _submit(hass, result, _input(**dict(zip(KEYS, (65, 65, 80, 90)))))
    assert result["errors"] == {"base": "invalid_mould_order"}
    assert all(key not in entry.options for key in KEYS[:2])                # nothing saved
    result = await _submit(hass, result, _input(**dict(zip(KEYS, (55, 62, 75, 85)))))
    assert result["step_id"] == "ventilation_settings"
    assert [entry.options[k] for k in KEYS] == [55, 62, 75, 85]
    result = await _open(hass, entry, "ventilation_settings", "model")
    assert _defaults(result) == dict(zip(KEYS, (55, 62, 75, 85)))            # shown again as saved


async def test_an_older_setup_keeps_its_limits_and_gets_lower_ones_below_them(hass) -> None:
    entry = _entry(rooms=[_room()], options={"mould_warn_surface_rh": 65, "mould_critical_surface_rh": 75})
    entry.add_to_hass(hass)
    result = await _open(hass, entry, "ventilation_settings", "model")
    assert _defaults(result) == dict(zip(KEYS, (60, 64, 65, 75)))
    result = await _submit(hass, result, _input())                            # saved unchanged
    assert result["step_id"] == "ventilation_settings"
    assert [entry.options[k] for k in KEYS] == [60, 64, 65, 75]


def test_unreadable_stored_values_fall_back_to_the_defaults() -> None:
    from custom_components.freshairiq.config_flow_schemas import _mould_lower_defaults
    assert _mould_lower_defaults({"mould_warn_surface_rh": "bad", "mould_slight_surface_rh": None}) == (60.0, 70.0)
    assert _mould_lower_defaults({"mould_warn_surface_rh": 62}) == (60.0, 61.0)
