"""Start values and the learning activity gate of a ventilation session.

Valid room values present at the opening are the frozen measurement basis even when
they are 30 minutes old. Learning and forecast validation need at least two real
sensor value changes between physical opening and close: 2x temperature, 2x humidity
or one of each. The end-to-end cases run the real coordinator on the golden harness
(Home Assistant stub, frozen clock, in-memory storage, no network).
"""
from __future__ import annotations

import asyncio
import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import coordinator_golden as golden  # noqa: E402 - installs the Home Assistant stub of the golden harness

from custom_components.freshairiq import coordinator_room_model  # noqa: E402
from custom_components.freshairiq.climate_sources import (  # noqa: E402
    advance_climate_report_activity,
    climate_changes_since,
    climate_reading,
    climate_report_snapshot,
)
from custom_components.freshairiq.localize import Translator  # noqa: E402
from custom_components.freshairiq.measurement_frame import (  # noqa: E402
    room_session_measurement_quality,
    session_measurement_quality,
    session_value_change_counts,
)
from custom_components.freshairiq.model import absolute_humidity  # noqa: E402
from custom_components.freshairiq.ventilation_result import finalise_ventilation_group  # noqa: E402

TZ = golden.TZ
START = datetime(2026, 11, 17, 12, 0, tzinfo=TZ)
T_C = {"device_class": "temperature", "unit_of_measurement": "°C"}
H_PCT = {"device_class": "humidity", "unit_of_measurement": "%"}
FEWER = "Weniger als zwei Messänderungen während der Lüftung"
COMP = ROOT / "custom_components" / "freshairiq"


# ------------------------------------------------------------------------------------------------ end-to-end harness

def _airing(during, *, after_close=(), moisture_source=False, monkeypatch=None):
    """Values 30 min old at the opening, the given in-session reports, then the physical close."""
    seen = []
    original = golden.coord_mod.FreshAirIQCoordinator._async_update_data

    async def capture(self):
        result = await original(self)
        seen.append({"room": copy.deepcopy(result["rooms"]["r"]), "mem": copy.deepcopy(self.store.data["rooms"]["r"]),
                     "last": copy.deepcopy(self.store.data.get("last_ventilation"))})
        return result

    if moisture_source:
        detect = coordinator_room_model.update_moisture_source

        def forced(mem, **kwargs):
            return {**detect(mem, **kwargs), "active": bool(mem.get("session_active"))}

        monkeypatch.setattr(coordinator_room_model, "update_moisture_source", forced)
    steps = [{"advance": 60} for _ in range(29)]
    steps.append({"advance": 60, "set": {"binary_sensor.r_f": "on"}})
    for values in during:
        steps.append({"advance": 60, "set": values} if values else {"advance": 60})
        steps.append({"advance": 60})  # coordinator refresh without a new report
    steps.append({"advance": 60, "set": {"binary_sensor.r_f": "off"}})
    for values in after_close:
        steps.append({"advance": 2, "set": values})
    steps += [{"advance": 5}, {"advance": 15}, {"advance": 60}]
    room = golden._room("r", "Raum", "ground_floor", temp=["sensor.r_t"], hum=["sensor.r_h"], contacts=["binary_sensor.r_f"], volume=50)
    initial = {"sensor.r_t": (21.0, T_C), "sensor.r_h": (65.0, H_PCT), "sensor.aussen_t": (5.0, T_C),
               "sensor.aussen_h": (70.0, H_PCT), "binary_sensor.r_f": ("off", {"device_class": "window"})}
    scenario = {"start": START, "initial": initial, "steps": steps, "options": dict(golden.BASE_OPTIONS),
                "data": {"outdoor_temperature": "sensor.aussen_t", "outdoor_humidity": "sensor.aussen_h", "rooms": [room],
                         "levels": ["ground_floor"]}}
    golden.coord_mod.FreshAirIQCoordinator._async_update_data = capture
    try:
        asyncio.run(golden._run_scenario("start-values", scenario, None))
    finally:
        golden.coord_mod.FreshAirIQCoordinator._async_update_data = original
    opened = next(i for i, cycle in enumerate(seen) if cycle["mem"].get("session_active"))
    closed = next(i for i, cycle in enumerate(seen) if i > opened and not cycle["mem"].get("session_active"))
    return seen[opened:closed], seen[closed:]


def _assert_original_start_basis(session):
    start_ah = absolute_humidity(21.0, 65.0)
    first = session[0]["mem"]
    assert first["session_start_frame_max_age_s"] >= 1800  # the valid start values were 30 minutes old
    for cycle in session:
        mem = cycle["mem"]
        assert mem["session_start_temp"] == 21.0 and mem["session_start_humidity"] == 65.0
        assert mem["session_start_ah"] == pytest.approx(start_ah)
        assert mem["session_learning_start_ah"] == pytest.approx(start_ah)
        assert mem["session_validation_start_ah"] == pytest.approx(start_ah)
        assert mem["session_validation_start_temp"] == 21.0
        assert mem["session_learning_started"] == mem["session_started"] == first["session_started"]
        assert mem["session_validation_started"] == first["session_started"]


@pytest.mark.parametrize("during", [
    pytest.param([{"sensor.r_t": 20.6}, {"sensor.r_t": 20.2}], id="2x-temperature"),
    pytest.param([{"sensor.r_h": 63.5}, {"sensor.r_h": 62.0}], id="2x-humidity"),
    pytest.param([{"sensor.r_t": 20.6}, {"sensor.r_h": 63.5}], id="temperature-and-humidity"),
])
def test_old_start_values_and_two_value_changes_pass_the_activity_gate(during):
    session, after = _airing(during)
    _assert_original_start_basis(session)
    assert room_session_measurement_quality(session[0]["mem"])["timestamp_gate_passed"] is False
    final = session[-1]
    quality = final["room"]["session_measurement_quality"]
    assert quality["timestamp_gate_passed"] is True and quality["eligible"] is True and quality["fresh_reports"] == 2
    assert final["room"]["measurement_frame_quality"] != "excellent"  # passes without synchronous start values
    mem, last = after[0]["mem"], after[0]["last"]
    assert mem["last_learning_valid"] is True and mem["diagnosis"].startswith("Learned")
    assert last["learning_valid_count"] == 1 and last["prediction_alignment_quality"] == "validated"
    assert last["prediction_exclusion_reason"] is None and last["measurement_exclusion_reason"] is None
    assert after[0]["room"]["session_measurement_quality"]["fresh_reports"] == 0  # idle rooms show no stale evidence


@pytest.mark.parametrize("during,after_close,raw_humidity_reports", [
    pytest.param([None, None], (), 0, id="no-change-only-coordinator-refreshes"),
    pytest.param([{"sensor.r_t": 20.6}, None], (), 0, id="one-change"),
    pytest.param([{"sensor.r_t": 20.6}] + [{"sensor.r_h": 65.0}] * 4, (), 4, id="unchanged-repeat-reports"),
    pytest.param([{"sensor.r_t": 20.6}], ({"sensor.r_t": 20.1}, {"sensor.r_h": 62.0}), 0, id="changes-only-after-close"),
    pytest.param([{"sensor.r_t": 20.6}, {"sensor.r_h": "unavailable"}, {"sensor.r_h": 65.0}], (), 2, id="unavailable-sensor"),
])
def test_missing_value_changes_keep_learning_and_validation_closed(during, after_close, raw_humidity_reports):
    session, after = _airing(during, after_close=after_close)
    _assert_original_start_basis(session)
    final = session[-1]
    quality = final["room"]["session_measurement_quality"]
    assert quality["timestamp_gate_passed"] is False and quality["eligible"] is False
    assert quality["reason"].startswith(FEWER)
    # The raw report counters that feed the close/plateau logic keep their meaning.
    assert final["mem"]["session_humidity_reports"] == raw_humidity_reports
    mem, last = after[0]["mem"], after[0]["last"]
    assert mem["last_learning_valid"] is False and FEWER in mem["diagnosis"]
    assert last["learning_valid_count"] == 0 and last["measurement_exclusion_reason"] == FEWER
    assert last["removed_ml"] is None


def test_active_moisture_source_stays_an_independent_exclusion(monkeypatch):
    session, after = _airing([{"sensor.r_t": 20.6}, {"sensor.r_h": 63.5}], moisture_source=True, monkeypatch=monkeypatch)
    _assert_original_start_basis(session)
    assert session[-1]["room"]["session_measurement_quality"]["timestamp_gate_passed"] is True
    mem, last = after[0]["mem"], after[0]["last"]
    assert mem["last_learning_valid"] is False and "Feuchtequelle" in mem["diagnosis"]
    assert last["learning_valid_count"] == 0 and last["moisture_source_contaminated_rooms"] == 1
    assert last["prediction_alignment_quality"] == "informational"
    assert last["prediction_exclusion_reason"] == "Aktive Feuchtequelle erkannt"
    assert last["prediction_status_text"].endswith("keine Genauigkeitswertung: Aktive Feuchtequelle erkannt")
    assert "synchron" not in last["prediction_status_text"]


# ------------------------------------------------------------------------------------------------ evidence per logical sensor

def _state(value, stamp, unit="°C"):
    return SimpleNamespace(state=str(value), attributes={"unit_of_measurement": unit}, last_reported=stamp, last_updated=stamp,
                           last_changed=stamp)


class _Hass:
    def __init__(self, states):
        self.states = SimpleNamespace(get=lambda entity_id: states.get(entity_id))


def test_climate_reading_accepts_only_plausible_numbers():
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    assert climate_reading(None, "temperature") is None
    assert climate_reading(_state("unavailable", now), "temperature") is None
    assert climate_reading(_state("abc", now), "humidity") is None
    assert climate_reading(_state("inf", now), "humidity") is None
    assert climate_reading(_state(68.0, now, "°F"), "temperature") == pytest.approx(20.0)
    assert climate_reading(_state(20.0, now, "°R"), "temperature") is None
    assert climate_reading(_state(80.0, now), "temperature") is None
    assert climate_reading(_state(55.0, now, "%"), "humidity") == 55.0
    assert climate_reading(_state(140.0, now, "%"), "humidity") is None


def test_value_changes_count_only_real_changes_inside_the_window():
    start = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)

    def row(t, h, t_at, h_at, available=True):
        return {"available": available, "reports": {"temperature": t_at.isoformat(), "humidity": h_at.isoformat()},
                "values": {"temperature": t, "humidity": h}, "changes": {}}

    state = {"0": row(21.0, 65.0, start - timedelta(minutes=30), start - timedelta(minutes=30))}
    counts = {}
    # unchanged repeat report: report counter advances, learning evidence does not
    state, counts, fresh = advance_climate_report_activity(state, counts, {"0": row(21.0, 65.0, start + timedelta(minutes=1), start - timedelta(minutes=30))}, window_start=start)
    assert counts == {"0": 1} and fresh == 1 and state["0"]["changes"] == {}
    # an invalid reading never counts and keeps the last valid value
    state, counts, _ = advance_climate_report_activity(state, counts, {"0": row(None, 65.0, start + timedelta(minutes=2), start - timedelta(minutes=30))}, window_start=start)
    assert state["0"]["changes"] == {} and state["0"]["values"]["temperature"] == 21.0
    # back with the same value: no change; a different value: one change
    state, counts, _ = advance_climate_report_activity(state, counts, {"0": row(21.0, 65.0, start + timedelta(minutes=3), start - timedelta(minutes=30))}, window_start=start)
    assert state["0"]["changes"] == {}
    state, counts, _ = advance_climate_report_activity(state, counts, {"0": row(20.5, 65.0, start + timedelta(minutes=4), start - timedelta(minutes=30))}, window_start=start)
    assert state["0"]["changes"] == {"temperature": 1}
    # a change after the physical close does not count
    end = start + timedelta(minutes=5)
    state, counts, _ = advance_climate_report_activity(state, counts, {"0": row(20.5, 63.0, start + timedelta(minutes=4), end + timedelta(seconds=1))}, window_start=start, window_end=end)
    assert state["0"]["changes"] == {"temperature": 1} and state["0"]["values"]["humidity"] == 63.0
    # corrupt stored evidence restarts at one instead of failing
    state["0"]["changes"] = {"humidity": "bad"}
    state, counts, _ = advance_climate_report_activity(state, counts, {"0": row(20.5, 61.0, start + timedelta(minutes=4), start + timedelta(minutes=4, seconds=30))}, window_start=start)
    assert state["0"]["changes"] == {"humidity": 1}
    # a legacy row without values only sets the baseline
    state, _, _ = advance_climate_report_activity({"0": {"reports": {}}}, {}, {"0": row(20.0, 60.0, start + timedelta(minutes=6), start + timedelta(minutes=6))}, window_start=start)
    assert state["0"]["changes"] == {} and state["0"]["values"] == {"temperature": 20.0, "humidity": 60.0}


def test_strongest_sensor_decides_and_changes_of_different_sensors_are_never_summed():
    room = {"session_active": True, "session_climate_report_state": {
        "0": {"available": True, "changes": {"temperature": 1}},
        "1": {"available": True, "changes": {"humidity": 1}},
        "2": {"available": False, "changes": {"temperature": 5}},
    }}
    assert session_value_change_counts(room) == (1, 1, 0)
    assert room_session_measurement_quality(room)["timestamp_gate_passed"] is False
    room["session_climate_report_state"]["1"]["changes"]["temperature"] = "bad"
    room["session_climate_report_state"]["1"]["changes"]["humidity"] = 2
    assert session_value_change_counts(room) == (2, 0, 2)
    assert room_session_measurement_quality(room)["timestamp_gate_passed"] is True
    # restored sessions without value tracking keep their stored counters; idle rooms show none
    legacy = {"session_active": True, "session_climate_report_state": {"0": {"reports": {}}}, "session_fresh_measurements": 2,
              "session_temperature_reports": 1, "session_humidity_reports": 1}
    assert session_value_change_counts(legacy) == (2, 1, 1)
    assert session_value_change_counts({**room, "session_active": False}) == (0, 0, 0)
    assert session_value_change_counts(None) == (0, 0, 0)
    assert room_session_measurement_quality(None)["eligible"] is False


def test_snapshot_and_opening_changes_ignore_repeats_invalid_values_and_clock_mismatch():
    opened = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    before, after = opened - timedelta(minutes=30), opened + timedelta(seconds=40)
    repeat = _state(55.0, after, "%")
    repeat.last_changed = before  # same value reported again after the opening
    hass = _Hass({"sensor.t1": _state(21.0, after), "sensor.h1": repeat, "sensor.t2": _state("unavailable", after),
                  "sensor.h2": _state(140.0, after, "%")})
    snapshot = climate_report_snapshot(hass, ["sensor.t1", "sensor.t2"], ["sensor.h1", "sensor.h2"])
    assert snapshot["0"]["values"] == {"temperature": 21.0, "humidity": 55.0} and snapshot["0"]["changes"] == {}
    assert snapshot["1"]["values"] == {"temperature": None, "humidity": None}
    changes = climate_changes_since(hass, ["sensor.t1", "sensor.t2"], ["sensor.h1", "sensor.h2", "sensor.h3"], opened)
    assert changes == {"0": {"temperature": 1}, "1": {}, "2": {}}
    assert climate_changes_since(hass, "sensor.t1", "", opened.replace(tzinfo=None)) == {"0": {}}


# ------------------------------------------------------------------------------------------------ reasons in result and dashboard

def _session(**extra):
    event = {"key": "r", "name": "Raum", "volume_m3": 50.0, "started_at": "2026-11-17T12:00:00+01:00",
             "ended_at": "2026-11-17T12:10:00+01:00", "duration_min": 10.0, "removed_ml": 100.0, "predicted_removed_ml": 90.0,
             "prediction_time_aligned": True, "prediction_comparable": False, "session_timestamp_activity_gate_passed": True}
    event.update(extra)
    return event


@pytest.mark.parametrize("extra,reason", [
    ({"moisture_source_contaminated": True}, "Aktive Feuchtequelle erkannt"),
    ({"reference_moisture_reversal": True}, "Referenzluft wurde während der Lüftung zu feucht"),
    ({"session_timestamp_activity_gate_passed": False}, FEWER),
    ({"outcome_feedback_reason": "Älterer Grund"}, "Älterer Grund"),
    ({}, "Messung nicht für die Genauigkeitswertung verwertbar"),
])
def test_excluded_forecast_comparison_reports_its_actual_reason(extra, reason):
    group = {"started_at": "2026-11-17T12:00:00+01:00", "sessions": [_session(**extra)]}
    result = finalise_ventilation_group(group, datetime.fromisoformat("2026-11-17T12:10:00+01:00"))
    assert result["prediction_alignment_quality"] == "informational"
    assert result["prediction_exclusion_reason"] == reason
    assert result["prediction_status_text"].endswith(f"keine Genauigkeitswertung: {reason}")
    assert "synchron" not in result["prediction_status_text"]


def test_untrusted_moisture_result_reports_its_actual_reason_once_per_house():
    sessions = [
        _session(key="a", moisture_measurement_valid=False, session_timestamp_activity_gate_passed=False),
        _session(key="b", moisture_measurement_valid=False, session_timestamp_activity_gate_passed=False),
        _session(key="c", moisture_measurement_valid=False, final_measurement_available=False),
        _session(key="d", moisture_measurement_valid=False),
        _session(key="e", prediction_comparable=True),
    ]
    result = finalise_ventilation_group({"started_at": "2026-11-17T12:00:00+01:00", "sessions": sessions},
                                        datetime.fromisoformat("2026-11-17T12:10:00+01:00"))
    assert result["measurement_exclusion_reason"] == f"{FEWER}; Keine verwertbare Abschlussmessung nach dem Schließen; Messung nicht verwertbar"
    assert result["prediction_alignment_quality"] == "validated" and result["prediction_exclusion_reason"] is None


def test_reasons_are_translated_for_english_installations_and_the_dashboard():
    translator = Translator()
    for german in (FEWER, "Aktive Feuchtequelle erkannt", "Referenzluft wurde während der Lüftung zu feucht",
                   "Keine verwertbare Abschlussmessung nach dem Schließen", "Messung nicht verwertbar",
                   session_measurement_quality(1)["reason"], session_measurement_quality(0)["reason"],
                   session_measurement_quality(2)["reason"],
                   f"Startprognose auf die tatsächliche Messdauer abgeglichen · keine Genauigkeitswertung: {FEWER}"):
        english = translator.text(german)
        assert english != german and not any(ch in english for ch in "äöüß")
    card = (COMP / "frontend" / "freshairiq-card.js").read_text(encoding="utf-8")
    english = (COMP / "frontend" / "freshairiq-card-i18n-en.js").read_text(encoding="utf-8")
    assert "last.prediction_exclusion_reason" in card and "last.measurement_exclusion_reason" in card
    assert "synchron" not in card[card.index("_ventilationResultCard(last"):card.index("_hero(st, rooms")]
    for phrase in ("Raum/Räume von der Genauigkeitswertung ausgeschlossen", "Keine Genauigkeitswertung",
                   "Dieser Vergleich wird nicht als Prognosegenauigkeit gewertet", "Messung nicht verwertbar",
                   "Messung nicht für die Genauigkeitswertung verwertbar",
                   "Feuchteergebnis nicht in Lernen oder Feuchtestatistik übernommen"):
        assert phrase in card and f'["{phrase}", "' in english
