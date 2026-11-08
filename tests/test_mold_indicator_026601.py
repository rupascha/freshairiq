"""v0.26.6.1 (#21): surface RH from Home Assistant's Mold Indicator helper – pure logic."""
from __future__ import annotations

from dataclasses import replace

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room, surface_relative_humidity
from custom_components.freshairiq.surface_source import SOURCE_HELPER, SOURCE_INTERNAL, helper_reading, source_fields

OPTIONS = dict(DEFAULT_OPTIONS)


def _room(**extra) -> RoomInput:
    # 21 °C, 58.5 % inside, 5 °C / 80 % outside: the internal estimate is 75 %
    return replace(RoomInput("dach", "Dachzimmer", 21.0, 58.5, 5.0, 80.0, 30.0, False, 0.0), **extra)


def test_helper_reading_takes_only_a_finite_percentage_of_a_mold_indicator() -> None:
    assert helper_reading("95", "%", "mold_indicator") == (95.0, "ok")
    assert helper_reading("0", "%", "mold_indicator") == (0.0, "ok")
    assert helper_reading("100", "%", None) == (100.0, "ok")          # unregistered YAML helper: value and unit checked
    assert helper_reading("95", "%", "mqtt") == (None, "not_mold_indicator")   # a room humidity sensor is never taken
    assert helper_reading(None, None, "mold_indicator") == (None, "missing")
    for state in ("unknown", "unavailable", ""):
        assert helper_reading(state, "%", "mold_indicator") == (None, "unavailable")
    assert helper_reading("95", "g/m³", "mold_indicator") == (None, "wrong_unit")
    assert helper_reading("95", None, "mold_indicator") == (None, "wrong_unit")
    for state in ("nan", "inf", "-inf", "abc"):
        assert helper_reading(state, "%", "mold_indicator") == (None, "invalid"), state
    for state in ("-0.1", "100.5", "250"):
        assert helper_reading(state, "%", "mold_indicator") == (None, "out_of_range"), state
    assert source_fields("sensor.dach_mold", 95.0, "ok") == {"surface_rh_source": SOURCE_HELPER, "surface_rh_source_entity": "sensor.dach_mold"}
    assert source_fields("sensor.dach_mold", None, "unavailable") == {"surface_rh_source": SOURCE_INTERNAL, "surface_rh_source_entity": "sensor.dach_mold",
                                                                       "surface_rh_source_issue": "unavailable"}


def test_without_a_helper_the_result_is_exactly_as_before() -> None:
    base = _room()
    assert round(surface_relative_humidity(21.0, 58.5, 5.0, OPTIONS["surface_factor"])) == 75
    assert evaluate_room(base, OPTIONS, False) == evaluate_room(replace(base, surface_rh_helper=None), OPTIONS, False)
    assert evaluate_room(base, OPTIONS, False).surface_rh == 75


def test_a_valid_helper_value_replaces_the_estimate_before_every_decision() -> None:
    internal = evaluate_room(_room(), OPTIONS, False)
    helper = evaluate_room(_room(surface_rh_helper=95.0), OPTIONS, False)
    assert (internal.surface_rh, internal.mould_level) == (75, "Elevated")
    assert (helper.surface_rh, helper.mould_level) == (95, "Very high")
    # the ventilation threshold and all limits stay as they are: the same advice here (no threshold reached)
    assert helper.action == internal.action == "Wait"
    # room air, absolute humidity and the ventilation physics are untouched
    for field in ("temperature", "humidity", "absolute_humidity", "water_in_air_ml", "potential_ml", "delta_g_m3"):
        assert getattr(helper, field) == getattr(internal, field), field
    # 0 and 100 are taken as they are
    assert evaluate_room(_room(surface_rh_helper=0.0), OPTIONS, False).mould_level == "Low"
    assert (lambda r: (r.surface_rh, r.mould_level))(evaluate_room(_room(surface_rh_helper=100.0), OPTIONS, False)) == (100, "Very high")


def test_the_helper_value_counts_before_the_urgency_rules() -> None:
    # humid room, dry mild outside air – airing is wanted, but a strict pollen veto holds it back …
    pollen = {**OPTIONS, "pollen_enabled": True, "pollen_strict_veto": True, "pollen_max": 4.0}
    room = _room(humidity=70.0, reference_temperature=12.0, reference_humidity=60.0, pollen_index=8.0)
    internal = evaluate_room(room, pollen, False)
    assert internal.mould_level == "High" and internal.action != "Ventilate"
    # … unless the surface is critical: the helper's 95 % makes it urgent and lifts the veto, like a critical estimate
    helper = evaluate_room(replace(room, surface_rh_helper=95.0), pollen, False)
    assert (helper.mould_level, helper.action) == ("Very high", "Ventilate")


def test_a_critical_helper_value_does_not_bypass_the_protection_against_counterproductive_airing() -> None:
    # outside air wetter than inside: airing would bring water in – the mould warning stays, no airing advice
    wet_outside = _room(reference_temperature=22.0, reference_humidity=90.0, surface_rh_helper=95.0)
    internal = evaluate_room(replace(wet_outside, surface_rh_helper=None), OPTIONS, False)
    result = evaluate_room(wet_outside, OPTIONS, False)
    assert result.mould_level == "Very high" and result.delta_g_m3 < 0
    assert (result.action, internal.action) == ("Do not ventilate", "Do not ventilate")
