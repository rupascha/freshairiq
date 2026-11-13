"""GitHub #18 (0.26.7.0): the dishwasher as a moisture source.

Phases: closed washing (little vapour reaches the room), drying (device-dependent, door ajar), door opening after the
end (short warm burst), after-evaporation (weaker, ends by the usual hysteresis). An optional Home Assistant signal
(drying binary sensor, programme/phase sensor) is used where present but never required. Without it the room climate
must match a specific pattern; otherwise only a general moisture source is named. The thresholds below are physical
reasoning, not fitted to user data (none was provided).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.freshairiq.const import (
    MOISTURE_SOURCE_COOKING, MOISTURE_SOURCE_DISHWASHER, MOISTURE_SOURCE_DRYER, MOISTURE_SOURCE_SHOWER,
    MOISTURE_SOURCE_WASHING_MACHINE, MOISTURE_SOURCES,
)
from custom_components.freshairiq.dishwasher import DRYING, FINISHED, IDLE, WASHING, dishwasher_phase
from custom_components.freshairiq.moisture_source import _identify_source, _source_signatures, update_moisture_source

T0 = datetime(2026, 11, 13, 19, 0, tzinfo=timezone.utc)
STEADY = {"samples": 6.0, "ah_monotonic": 1.0, "temp_monotonic": 1.0, "peak_ah_rate": 0.1}


@pytest.mark.parametrize(("entity", "state", "phase"), [
    ("binary_sensor.gs_trocknen", "on", DRYING), ("binary_sensor.gs_trocknen", "off", IDLE),
    ("sensor.gs_phase", "Drying", DRYING), ("sensor.gs_phase", "Trocknen", DRYING), ("sensor.gs_phase", "eco_dry", DRYING),
    ("sensor.gs_phase", "Main wash", WASHING), ("sensor.gs_phase", "Rinse", WASHING), ("select.gs", "Spülen", WASHING),
    ("sensor.gs_phase", "Finished", FINISHED), ("sensor.gs_phase", "Programm beendet", FINISHED),
    ("sensor.gs_phase", "Ready", IDLE), ("sensor.gs_phase", "inactive", IDLE),
    ("sensor.gs_phase", "unavailable", None), ("sensor.gs_phase", "Strange", None), ("sensor.gs_phase", "pending", None),
])
def test_device_signal_phases(entity, state, phase):
    assert dishwasher_phase(entity, state) == phase


def test_new_source_is_selectable():
    assert MOISTURE_SOURCE_DISHWASHER in MOISTURE_SOURCES


def _match(configured, *, ah_rise, temp_rise, rate, generated, pattern=STEADY):
    return _source_signatures(set(configured), ah_rise=ah_rise, temp_rise=temp_rise, source_rate=rate,
                              generated_ml=generated, pattern=pattern)


def test_climate_pattern_of_a_door_opening_names_the_dishwasher():
    matches = _match([MOISTURE_SOURCE_DISHWASHER, MOISTURE_SOURCE_COOKING], ah_rise=0.3, temp_rise=0.2, rate=3.5, generated=18)
    assert matches == [MOISTURE_SOURCE_DISHWASHER]
    assert _identify_source(matches)[0] == "Geschirrspüler"


@pytest.mark.parametrize(("label", "kw"), [
    ("cooking", dict(ah_rise=0.35, temp_rise=0.8, rate=5.0, generated=30)),      # more heat than a dishwasher
    ("shower", dict(ah_rise=0.9, temp_rise=0.3, rate=9.0, generated=60)),        # far more water
    ("people", dict(ah_rise=0.08, temp_rise=0.05, rate=1.0, generated=6)),       # occupants breathing
    ("dryer", dict(ah_rise=0.2, temp_rise=0.9, rate=3.0, generated=20)),
])
def test_other_loads_are_not_called_dishwasher(label, kw):
    assert MOISTURE_SOURCE_DISHWASHER not in _match([MOISTURE_SOURCE_DISHWASHER], **kw), label


def test_ambiguous_with_a_washing_machine_stays_a_general_source():
    matches = _match([MOISTURE_SOURCE_DISHWASHER, MOISTURE_SOURCE_WASHING_MACHINE], ah_rise=0.3, temp_rise=0.2, rate=3.0, generated=18)
    assert set(matches) == {MOISTURE_SOURCE_DISHWASHER, MOISTURE_SOURCE_WASHING_MACHINE}
    assert _identify_source(matches)[1] is None and _identify_source(matches)[0] == "Feuchtequelle"


def test_not_configured_means_not_named():
    assert MOISTURE_SOURCE_DISHWASHER not in _match([MOISTURE_SOURCE_DRYER, MOISTURE_SOURCE_SHOWER], ah_rise=0.3, temp_rise=0.2, rate=3.5, generated=18)


def _update(mem, now, ah, *, phase=None, configured=(MOISTURE_SOURCE_DISHWASHER,)):
    return update_moisture_source(mem, now=now, absolute_humidity_g_m3=ah, reference_ah_g_m3=6.0, temperature_c=21.0,
                                  volume_m3=30.0, window_open=False, learning_rate_per_min=0.03, airflow_factor=1.0,
                                  cross_ventilation=False, configured_sources=list(configured), device_phase=phase)


def test_device_signal_drying_counts_at_once_and_ends_by_hysteresis():
    mem: dict = {}
    assert _update(mem, T0, 9.0, phase=WASHING)["active"] is False          # closed washing: nothing assumed
    state = _update(mem, T0 + timedelta(minutes=1), 9.0, phase=DRYING)
    assert state["active"] is True and state["identified_source"] == MOISTURE_SOURCE_DISHWASHER and state["label"] == "Geschirrspüler"
    # drying over, climate quiet: the usual six quiet minutes end it, then recovery (follow-up) runs
    _update(mem, T0 + timedelta(minutes=3), 9.0, phase=IDLE)
    ended = _update(mem, T0 + timedelta(minutes=9), 9.0, phase=IDLE)
    assert ended["active"] is False and ended["recovery"] is True


def test_finished_signal_names_a_measured_rise_without_assuming_one():
    mem: dict = {}
    assert _update(mem, T0, 9.0, phase=FINISHED)["active"] is False          # no rise measured: nothing assumed
    _update(mem, T0 + timedelta(minutes=1), 9.0, phase=FINISHED, configured=())
    # a strong unspecified rise after the end (door opened) is attributed to the dishwasher by the signal
    for minute, ah in ((3, 9.6), (5, 10.4), (7, 11.2)):
        state = _update(mem, T0 + timedelta(minutes=minute), ah, phase=FINISHED, configured=())
    assert state["active"] is True and state["identified_source"] == MOISTURE_SOURCE_DISHWASHER
