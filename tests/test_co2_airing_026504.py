"""0.26.5.4 (review A07, owner decision): CO2 from the warning threshold asks for an airing of its own.

Before, a room at 1220 ppm (warning 1000 ppm) with only a small drying difference
was told "Wait – airing not effective enough", the CO2 goal disappeared behind the
humidity start threshold. Guard rails: only with the CO2 goal active, not when the
reference air is clearly wetter (more than ``close_delta``), pollen/fine dust still
veto, the critical threshold stays the health override, 50 ppm hysteresis.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import CO2_HYSTERESIS_PPM, RoomInput, co2_lead, evaluate_room
from custom_components.freshairiq.room_recommendation import _recommendation

OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400}


def _room(co2, *, ref_rh=55.0, rh=50.0, latched=False, **extra) -> RoomInput:
    values = dict(key="wz", name="Wohnzimmer", temperature=21.0, humidity=rh, reference_temperature=12.0, reference_humidity=ref_rh,
                  volume_m3=60.0, contact_open=False, contact_open_seconds=None, learning_rate=0.03, co2=co2, co2_lead_latched=latched)
    values.update(extra)
    return RoomInput(**values)


def _advice(co2, options=OPTIONS, pollen=0.0, **room):
    result = evaluate_room(_room(co2, **room), options, False)
    action, _reason, reasons = _recommendation(result, options, pollen=pollen, co2=co2, airflow=1.0, wind_bearing=None,
                                               wind_speed=None, co2_latched=bool(room.get("latched")))
    return result, action, reasons


@pytest.mark.parametrize(("co2", "airing"), [(950, False), (999, False), (1000, True), (1049, True), (1220, True)])
def test_from_the_warning_threshold_co2_asks_for_airing(co2, airing) -> None:
    result, action, reasons = _advice(co2)
    assert result.co2_airing is airing and result.ventilation_candidate is airing
    assert (action == "Ventilate") is airing
    if airing:
        assert reasons[0].startswith(f"CO₂ {co2} ppm liegt über der Warnschwelle") and reasons[1] == "Lüften senkt das CO₂; kurz und kräftig lüften genügt"


def test_the_reported_case_is_no_longer_wait() -> None:
    # review: 1220 ppm, warning 1000, drying difference about 0.9 g/m³, no cooling chance
    result, action, reasons = _advice(1220, ref_rh=77.0)
    assert 0 < result.delta_g_m3 < 2.5 and not result.cooling_candidate
    assert action == "Ventilate" and "Lüften noch nicht wirksam genug" not in " ".join(reasons)


def test_clearly_wetter_air_keeps_wait_with_the_co2_reason() -> None:
    slightly = _advice(1220, ref_rh=70.0, rh=40.0)
    assert -0.4 <= slightly[0].delta_g_m3 < 0 and slightly[1] == "Ventilate"
    assert slightly[2][1].startswith("Lüften senkt das CO₂; die etwas feuchtere Außenluft")
    wetter = _advice(1220, ref_rh=80.0, rh=40.0)
    assert wetter[0].delta_g_m3 < -0.4 and wetter[0].co2_airing is False
    assert wetter[1] in {"Wait", "Do not ventilate"} and wetter[2][0].startswith("CO₂ 1220 ppm")


def test_goal_off_pollen_and_critical_level() -> None:
    off = _advice(None)
    assert off[0].co2_airing is False and off[1] != "Ventilate"
    pollen = _advice(1220, options={**OPTIONS, "pollen_enabled": True, "pollen_max": 2}, pollen=4.0, pollen_index=4.0)
    assert pollen[1] == "Do not ventilate" and pollen[2][0].startswith("CO₂ 1220 ppm")
    critical = _advice(1500)
    assert critical[0].co2_airing is False and critical[0].ventilation_candidate and critical[1] == "Ventilate"
    assert critical[2][0].startswith("CO₂ 1500 ppm ist kritisch")


def test_a_humid_room_stays_a_moisture_airing() -> None:
    result, action, reasons = _advice(1220, rh=70.0, ref_rh=60.0)
    assert result.ventilation_candidate and result.co2_airing is False and action == "Ventilate"
    assert any("trockener (mindestens" in r for r in reasons)


def test_hysteresis_50_ppm_below_the_warning_threshold() -> None:
    band = 1000 - CO2_HYSTERESIS_PPM / 2
    latched = _advice(band, latched=True)
    assert latched[1] == "Ventilate" and "knapp unter der Warnschwelle 1000 ppm" in latched[2][0]
    assert _advice(band)[1] != "Ventilate"  # never reached the warning level: no CO2 airing
    assert _advice(1000 - CO2_HYSTERESIS_PPM - 1, latched=True)[1] != "Ventilate"
    assert co2_lead(None, OPTIONS, True) is False
    # with cooling possible as well, the cooling is the extra benefit
    cool = _advice(1220, temperature=26.0, reference_temperature=15.0, ref_rh=60.0, rh=40.0)
    assert cool[0].co2_airing and cool[1] == "Ventilate" and cool[2][-1].startswith("Zusätzlich kühlt")


def test_a_co2_airing_ends_once_co2_is_down_unless_something_else_needs_the_air() -> None:
    from custom_components.freshairiq.model import _co2_airing_done

    running = dict(session_active=True, session_co2_only=True)
    assert _co2_airing_done(_room(940, **running), OPTIONS, False, keep_open=False) is True
    assert _co2_airing_done(_room(970, latched=True, **running), OPTIONS, False, keep_open=False) is False  # hysteresis band
    assert _co2_airing_done(_room(940, **running), OPTIONS, True, keep_open=False) is False  # now a humidity case
    assert _co2_airing_done(_room(940, **running), OPTIONS, False, keep_open=True) is False  # cooling / source / protection
    assert _co2_airing_done(_room(940, session_active=True), OPTIONS, False, keep_open=False) is False  # not a CO2 airing
    assert _co2_airing_done(_room(None, **running), OPTIONS, False, keep_open=False) is True  # goal switched off meanwhile


def test_a_finished_co2_airing_is_not_released_again_by_its_drying_effect() -> None:
    """A fan-aired room: once CO2 is down the airing is closed and stays closed although the fan still dries."""
    opts = {**OPTIONS, "min_duration_min": 3, "max_duration_min": 60}
    room = dict(temperature=21.0, reference_temperature=21.0, ref_rh=30.0, rh=55.0, contact_open=True, contact_open_seconds=600,
                session_active=True, session_elapsed_min=8.0, session_start_temp=21.0, session_fresh_measurements=3,
                session_co2_only=True, mechanical_only=True)
    first = evaluate_room(_room(900, **room), opts, False)
    assert first.close_recommended and first.moisture_effect_next_5_min_ml > 31  # still drying well, but the CO2 job is done
    again = evaluate_room(_room(880, close_notified=True, **room), opts, False)
    assert again.close_recommended and again.action == "Close"


def test_enumerated_goals_are_translated_item_by_item() -> None:
    from custom_components.freshairiq.localize import Translator

    t = Translator(set())
    assert t.text("Aktuell erreichbar: Entfeuchtung, CO₂/Luftqualität, Temperaturkomfort") == \
        "Currently achievable: Dehumidification, CO₂/air quality, Temperature comfort"
    assert t.text("Aktuell erreichbar: CO₂/Luftqualität") == "Currently achievable: CO₂/air quality"
    assert t.text("Aktuell erreichbar: Entfeuchtung, Rasen mähen") == "Aktuell erreichbar: Entfeuchtung, Rasen mähen"  # unknown German stays
