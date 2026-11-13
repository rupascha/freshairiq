"""#29 (0.26.7.0): configurable absolute CO2 release level.

Before, a started CO2 airing ended 50 ppm below the warning threshold (1450 ppm with ``co2_warn`` 1500) – a
band crossed within seconds. ``co2_release`` (ppm, 0 = automatic) sets the absolute level down to which the
airing keeps going; it applies everywhere ``co2_lead`` is used (held, CO2 airing, airing done, cooling lead).
The default keeps today's behaviour exactly.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.localize import to_english
from custom_components.freshairiq.model import RoomInput, _co2_airing_done, co2_lead, co2_release_ppm, evaluate_room
from custom_components.freshairiq.room_recommendation import _recommendation
from custom_components.freshairiq.settings_contract import NATIVE_OPTION_KEYS
from custom_components.freshairiq.validation import option_relationship_error, repair_option_relationships

BASE = {**DEFAULT_OPTIONS, "co2_warn": 1500, "co2_critical": 2000}


def _room(co2, *, latched=False, **extra) -> RoomInput:
    values = dict(key="sz", name="Schlafzimmer", temperature=21.0, humidity=50.0, reference_temperature=12.0,
                  reference_humidity=55.0, volume_m3=40.0, contact_open=False, contact_open_seconds=None,
                  learning_rate=0.03, co2=co2, co2_lead_latched=latched)
    values.update(extra)
    return RoomInput(**values)


def test_default_is_automatic_and_keeps_the_previous_50_ppm_band():
    assert DEFAULT_OPTIONS["co2_release"] == 0.0
    assert co2_release_ppm(BASE) == 1450.0
    assert co2_lead(1460, BASE, True) is True and co2_lead(1440, BASE, True) is False
    assert co2_release_ppm({"co2_warn": 1000}) == 950.0  # older setups without the key


@pytest.mark.parametrize(("co2", "latched", "lead"), [
    (1500, False, True), (1499, False, False),   # start unchanged: the warning threshold
    (1200, True, True), (751, True, True), (750, True, True), (749, True, False),
])
def test_configured_release_holds_a_started_airing_down_to_the_absolute_level(co2, latched, lead):
    options = {**BASE, "co2_release": 750}
    assert co2_lead(co2, options, latched) is lead


def test_release_never_sits_at_or_above_the_warning_threshold_at_runtime():
    assert co2_release_ppm({**BASE, "co2_release": 1600}) == 1499.0
    assert co2_release_ppm({**BASE, "co2_release": "bad"}) == 1450.0
    assert co2_release_ppm({**BASE, "co2_release": float("nan")}) == 1450.0


def test_co2_only_airing_is_not_closed_at_1450_ppm_any_more():
    options = {**BASE, "co2_release": 750}
    running = dict(session_active=True, session_co2_only=True)
    assert _co2_airing_done(_room(1127, latched=True, **running), options, False, keep_open=False) is False
    assert _co2_airing_done(_room(740, latched=True, **running), options, False, keep_open=False) is True
    # without the option the previous behaviour stays: done below 1450 ppm
    assert _co2_airing_done(_room(1127, latched=True, **running), BASE, False, keep_open=False) is True


def test_room_keeps_asking_for_air_inside_the_release_band_with_the_level_in_the_reason():
    options = {**BASE, "co2_release": 750}
    result = evaluate_room(_room(1127, latched=True), options, False)
    assert result.co2_airing is True
    action, _reason, reasons = _recommendation(result, options, pollen=0.0, co2=1127, airflow=1.0, wind_bearing=None,
                                               wind_speed=None, co2_latched=True)
    assert action == "Ventilate"
    assert reasons[0] == "CO₂ 1127 ppm liegt unter der Warnschwelle 1500 ppm; die Empfehlung endet erst unter 750 ppm"
    assert to_english(reasons[0]) == "CO₂ 1127 ppm is below the warning threshold of 1500 ppm; the recommendation only ends below 750 ppm"


def test_default_reason_text_is_unchanged():
    result = evaluate_room(_room(1470, latched=True), BASE, False)
    _action, _reason, reasons = _recommendation(result, BASE, pollen=0.0, co2=1470, airflow=1.0, wind_bearing=None,
                                                wind_speed=None, co2_latched=True)
    assert reasons[0] == "CO₂ 1470 ppm liegt knapp unter der Warnschwelle 1500 ppm; die Empfehlung endet erst 50 ppm darunter"


@pytest.mark.parametrize(("release", "error"), [
    (0, None), (750, None), (400, None), (1450, None), (399, "invalid_co2_release"), (1500, "invalid_co2_release"),
    (1800, "invalid_co2_release"),
])
def test_new_writes_are_validated(release, error):
    assert option_relationship_error({"co2_warn": 1500, "co2_critical": 2000, "co2_release": release}) == error


def test_a_release_that_no_longer_fits_falls_back_to_automatic_on_repair():
    assert repair_option_relationships({"co2_warn": 900, "co2_critical": 1400, "co2_release": 950})["co2_release"] == 0.0
    assert repair_option_relationships({"co2_warn": 1500, "co2_critical": 2000, "co2_release": 750})["co2_release"] == 750


def test_option_is_a_native_setting():
    assert "co2_release" in NATIVE_OPTION_KEYS
