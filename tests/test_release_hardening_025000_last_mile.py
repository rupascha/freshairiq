from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import custom_components.freshairiq.consolidation as consolidation
import custom_components.freshairiq.decision as decision
import custom_components.freshairiq.forecast as forecast
import custom_components.freshairiq.forecast_backtest as backtest
import custom_components.freshairiq.forecast_validation as fv
import custom_components.freshairiq.intervention as intervention
import custom_components.freshairiq.learning_components as learning_components
import custom_components.freshairiq.live_coach as live_coach
import custom_components.freshairiq.measurement_frame as measurement_frame
import custom_components.freshairiq.model as model
import custom_components.freshairiq.moisture_source as moisture_source
import custom_components.freshairiq.opening_strategy as opening_strategy
import custom_components.freshairiq.passive_ventilation as passive_ventilation
import custom_components.freshairiq.personal_context as personal_context
import custom_components.freshairiq.planner as planner
import custom_components.freshairiq.post_stabilization as post_stabilization
import custom_components.freshairiq.presence as presence
import custom_components.freshairiq.recommendation as recommendation
import custom_components.freshairiq.robustness as robustness
from custom_components.freshairiq.const import (
    DEFAULT_OPTIONS,
    MOISTURE_SOURCE_COOKING,
    MOISTURE_SOURCE_SAUNA,
)


def _options(**overrides):
    out = dict(DEFAULT_OPTIONS)
    out.update(overrides)
    return out


def _room(**overrides):
    room = {
        "key": "r",
        "name": "Raum",
        "data_quality": "ok",
        "calculation_enabled": True,
        "active": False,
        "humidity": 60.0,
        "temperature": 21.0,
        "absolute_humidity": 10.0,
        "reference_absolute_humidity": 7.0,
        "delta_g_m3": 3.0,
        "volume_m3": 50.0,
        "potential_ml": 150.0,
        "realistic_potential_ml": 150.0,
        "surface_rh": 70.0,
        "co2": 700.0,
        "co2_available": True,
        "learned_exchange_rate_per_min": 0.03,
        "airflow_factor": 1.0,
        "forecast_confidence": 80,
        "forecast_5_min_moisture_effect_ml": 50.0,
        "forecast_5_min_temperature_change_c": -0.2,
        "temp_next_5_min_c": -0.2,
        "forecast_temperature_change_c": -0.2,
        "forecast_cost": 0.0,
        "next_5_min_cost": 0.0,
        "action": "Ventilate",
    }
    room.update(overrides)
    return room


def _opening(name: str, *, available=True, candidate=True, effect=30.0, delta=2.0, temp=-0.2, is_open=False):
    return {
        "name": name,
        "entity_id": f"binary_sensor.{name.lower()}",
        "available": available,
        "ventilation_candidate": candidate,
        "cooling_candidate": False,
        "moisture_effect_next_5_min_ml": effect,
        "delta_g_m3": delta,
        "temperature_effect_next_5_min_c": temp,
        "is_open": is_open,
        "source_label": "Außenluft",
    }


def test_consolidation_summer_cooling_close_guard():
    rooms = {
        "r": _room(
            active=True,
            action="Close",
            close_recommended=True,
            session_elapsed_min=5,
            forecast_5_min_moisture_effect_ml=20,
            forecast_5_min_temperature_change_c=-2,
            efficiency_ml_per_01c=1,
        )
    }
    out = consolidation.stabilise_recommendation(
        {"kind": "close", "room_keys": ["r"]}, rooms,
        _options(operating_profile="summer_cooling", min_return_next_5_min_ml=50),
    )
    assert out["kind"] == "close"


def test_decision_can_choose_non_weather_wait_without_false_weather_reason(monkeypatch):
    rooms = {"r": _room(outcome_feedback_samples=0)}

    def adjustment(selected, option_id, duration, pressure):
        # Deliberately make a simulated delayed option materially better while
        # keeping future weather absent. This verifies the hysteresis/result path.
        return {
            "strategy_bonus": -20.0 if option_id == "now" else 20.0,
            "strategy_maturity": 0.0,
            "strategy_follow_probability": 0.0,
        }

    monkeypatch.setattr(decision, "_strategy_adjustment", adjustment)
    out = decision.build_decision_simulation(
        rooms,
        _options(min_potential_room_ml=100),
        {"kind": "ventilate", "room_keys": ["r"], "duration_min": 5, "reasons": []},
        future_outdoor=None,
        now=datetime(2026, 9, 15, 9, 0),
    )
    assert out["kind"] == "wait"
    assert any("beste simulierte Option" in reason for reason in out["reasons"])
    assert out["future_weather_used"] is False


def test_forecast_next_non_wrap_night_after_today_start():
    now = datetime(2026, 9, 15, 18, 0)
    start, end = forecast.night_interval_bounds(now, "09:00", "17:00")
    assert start.date() == (now + timedelta(days=1)).date()
    assert end > start


def test_backtest_observe_exact_band_and_validation_skips_bad_room():
    samples = [
        {"magnitude_accuracy_percent": 70, "direction_correct": i % 2 == 0, "forecast_confidence": 70}
        for i in range(20)
    ]
    result = backtest._reliability_summary(samples)
    assert result["status"] == "Beobachten"
    assert 65 <= result["score_percent"] < 78

    now = datetime.now()
    summary = fv.validation_summary([
        {
            "valid": True,
            "ended_at": now.isoformat(),
            "room_results": ["bad", {"comparable": False, "key": "r"}],
        }
    ])
    assert summary["rooms"] == []


def test_intervention_invalid_service_and_humidifier_branch():
    assert intervention._service_for_turn_on(None) is None
    assert intervention._service_for_turn_on("invalid") is None
    items = intervention.build_interventions(
        room=_room(humidity=30),
        config={"humidifier": "humidifier.office"},
        options=_options(humidify_below_rh=35),
    )
    assert any(x["key"] == "humidify" for x in items)


def test_learning_status_middle_bands_and_overall_stage_mapper(monkeypatch):
    assert learning_components._status(80, 1) == "Sehr gut eingelernt"
    assert learning_components._status(70, 1) == "Eingelernt"

    # Isolate the final stage mapper: component computation itself has separate
    # tests. Every adaptive component is forced to the same evidence maturity.
    target = {"value": 30.0}

    def component(key, label, samples, maturity, target_samples, detail, *, description,
                  observation_only=False, quality_percent=None):
        row = {
            "key": key,
            "label": label,
            "samples": 1,
            "target_samples": 1,
            "maturity_percent": target["value"],
            "status": "test",
            "description": description,
            "detail": detail,
            "observation_only": observation_only,
        }
        if key == "forecast_validation":
            row["quality_percent"] = 90.0
        elif quality_percent is not None:
            row["quality_percent"] = quality_percent
        return row

    monkeypatch.setattr(learning_components, "_component", component)
    expected = [
        (30.0, "muster_erkannt"),
        (50.0, "bestaetigt"),
        (70.0, "eingelernt"),
        (80.0, "sehr_gut_eingelernt"),
    ]
    for maturity, stage in expected:
        target["value"] = maturity
        out = learning_components.build_learning_components_status(
            [{"calculation_enabled": True}], {}, forecast_backtest={}
        )
        # Without objective validation samples, the v4 maturity gate deliberately
        # caps the overall stage at "Beobachtet" regardless of component convergence.
        assert out["stage_key"] == "beobachtet"


def test_live_coach_baseline_fallback_and_fast_progress_shortening():
    opts = _options(min_duration_min=3, max_duration_min=20, min_return_next_5_min_ml=25)
    baseline = {
        "r": _room(
            active=True,
            session_elapsed_min=3,
            session_recommended_duration_min=10,
            session_predicted_removed_ml=10,
            result_ml=0,
            forecast_5_min_moisture_effect_ml=50,
            close_decision_ready=False,
        )
    }
    out = live_coach.refine_live_recommendation(baseline, opts, {"kind": "continue", "duration_min": 7})
    assert out["live_coach"] is True

    fast = {
        "r": _room(
            active=True,
            session_elapsed_min=5,
            session_recommended_duration_min=10,
            session_predicted_removed_ml=100,
            result_ml=70,
            forecast_5_min_moisture_effect_ml=80,
            forecast_5_min_confidence=90,
            outcome_feedback_samples=12,
            close_decision_ready=False,
        )
    }
    out2 = live_coach.refine_live_recommendation(fast, opts, {"kind": "continue", "duration_min": 5})
    assert out2["live_coach_state"] == "shortened"
    assert "schneller" in out2["live_coach_reason"]


def test_measurement_frame_missing_timestamps_are_stale():
    now = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
    assert measurement_frame._age_seconds(now, SimpleNamespace()) is None
    state = SimpleNamespace(last_reported=now - timedelta(seconds=10))
    missing = SimpleNamespace()
    out = measurement_frame.build_measurement_frame(
        now,
        temperature_state=state,
        humidity_state=missing,
        reference_temperature_state=state,
        reference_humidity_state=state,
    )
    assert out["quality"] == "stale"
    assert "Zeitstempel" in out["reason"]


def test_model_running_early_future_close_sensor_close_and_closed_states():
    opts = _options()
    early = model.RoomInput(
        key="early", name="Early", temperature=21, humidity=70,
        reference_temperature=10, reference_humidity=40, volume_m3=50,
        contact_open=True, contact_open_seconds=120, session_active=True,
        session_elapsed_min=1, session_start_temp=21,
    )
    early_result = model.evaluate_room(early, opts, False)
    assert isinstance(early_result.as_dict(), dict)

    # Model fallback after 15 min with a forecast reference near room AH.
    fallback = model.RoomInput(
        key="fallback", name="Fallback", temperature=21, humidity=60,
        reference_temperature=21, reference_humidity=59, volume_m3=50,
        contact_open=True, contact_open_seconds=1000, session_active=True,
        session_elapsed_min=16, session_start_temp=21,
        session_fresh_measurements=0,
        future_reference_temperature_15=21, future_reference_humidity_15=60,
    )
    fb = model.evaluate_room(fallback, opts, False)
    assert fb.action == "Close"
    assert fb.future_moisture_risk_15 is True
    assert fb.close_decision_model_fallback is True

    confirmed = model.RoomInput(
        key="confirmed", name="Confirmed", temperature=21, humidity=60,
        reference_temperature=21, reference_humidity=59, volume_m3=50,
        contact_open=True, contact_open_seconds=400, session_active=True,
        session_elapsed_min=5, session_start_temp=21, session_fresh_measurements=2,
    )
    cr = model.evaluate_room(confirmed, opts, False)
    assert cr.action == "Close"
    assert cr.close_decision_model_fallback is False

    wetter_ref = model.RoomInput(
        key="wet", name="Wet ref", temperature=21, humidity=40,
        reference_temperature=21, reference_humidity=60, volume_m3=50,
        contact_open=False, contact_open_seconds=0,
    )
    assert model.evaluate_room(wetter_ref, opts, False).action == "Do not ventilate"

    equal = model.RoomInput(
        key="equal", name="Equal", temperature=21, humidity=50,
        reference_temperature=21, reference_humidity=50, volume_m3=50,
        contact_open=False, contact_open_seconds=0,
    )
    assert model.evaluate_room(equal, opts, False).action == "Okay"


def test_moisture_source_identification_corrupt_history_and_hysteresis():
    generic = moisture_source._identify_source(set(), temp_rise=0, source_rate=5, generated_ml=30)
    assert generic[1] is None
    sauna = moisture_source._identify_source(
        {MOISTURE_SOURCE_SAUNA, MOISTURE_SOURCE_COOKING},
        temp_rise=1.0, source_rate=3.0, generated_ml=20,
    )
    assert sauna[1] == MOISTURE_SOURCE_SAUNA

    now = datetime(2026, 9, 15, 9, 0)
    base = {"at": (now - timedelta(minutes=5)).isoformat(), "ah": 10.0, "ref_ah": 7.0, "temp": 21.0, "open": False}
    memory = {
        "moisture_source_points": [{"at": "broken", "ah": 9.9, "ref_ah": 7, "temp": 21, "open": False}, base],
        "moisture_source_active": True,
        "moisture_source_confidence": 80,
        "moisture_source_rate_ml_min": 2,
        "moisture_source_generated_ml": 10,
        "moisture_source_label": "Feuchtequelle",
        "moisture_source_last_positive_at": (now - timedelta(minutes=7)).isoformat(),
    }
    out = moisture_source.update_moisture_source(
        memory, now=now, absolute_humidity_g_m3=10.0, reference_ah_g_m3=7.0,
        temperature_c=21.0, volume_m3=50, window_open=False,
        learning_rate_per_min=0.03, airflow_factor=1.0, cross_ventilation=False,
        configured_sources=[],
    )
    assert out["active"] is False

    recent = dict(memory)
    recent["moisture_source_points"] = [base]
    recent["moisture_source_active"] = True
    recent["moisture_source_confidence"] = 80
    recent["moisture_source_last_positive_at"] = (now - timedelta(minutes=2)).isoformat()
    out2 = moisture_source.update_moisture_source(
        recent, now=now, absolute_humidity_g_m3=10.0, reference_ah_g_m3=7.0,
        temperature_c=21.0, volume_m3=50, window_open=False,
        learning_rate_per_min=0.03, airflow_factor=1.0, cross_ventilation=False,
        configured_sources=[],
    )
    assert out2["active"] is True
    assert out2["confidence"] == 77


def test_opening_strategy_all_defensive_and_running_paths():
    assert opening_strategy._opening_score(_opening("Cool", effect=10, temp=-2), "summer_cooling") == 22
    assert opening_strategy._room_opening_plan(
        {"opening_assessments": [_opening("A", available=False)]}, "comfort", running=False
    ) is None
    assert opening_strategy._room_opening_plan(
        {"opening_assessments": [_opening("A", candidate=False, effect=0, delta=1)]}, "comfort", running=False
    ) is None
    assert opening_strategy._room_opening_plan(
        {"opening_assessments": [_opening("A", is_open=True)]}, "comfort", running=True
    ) is None

    assert opening_strategy.enrich_opening_recommendation("bad", {}, {}) == "bad"
    marker = {"kind": "okay"}
    assert opening_strategy.enrich_opening_recommendation(marker, {}, {}) is marker
    empty = {"kind": "ventilate", "room_keys": []}
    assert opening_strategy.enrich_opening_recommendation(empty, {}, {}) is empty
    bad_room = {"kind": "ventilate", "room_keys": ["x"]}
    assert opening_strategy.enrich_opening_recommendation(bad_room, {"x": "bad"}, {}) is bad_room

    # In a multi-room close, a recovery plan for only one room must not partially
    # override the canonical close action.
    good = _opening("Good", effect=30, delta=2, is_open=True)
    bad = _opening("Bad", effect=-10, delta=-1, is_open=True)
    rooms = {
        "a": _room(key="a", name="A", active=True, delta_g_m3=0.3, opening_assessments=[good, bad]),
        "b": _room(key="b", name="B", active=True, delta_g_m3=0.3, opening_assessments=[]),
    }
    rec = {"kind": "close", "room_keys": ["a", "b"], "status": "close_windows"}
    out = opening_strategy.enrich_opening_recommendation(rec, rooms, _options(close_delta=0.4))
    assert out["kind"] == "close"


def test_passive_ventilation_bad_samples_too_few_unstable_and_low_confidence():
    common = dict(
        start_ah=10.0, current_ah=9.8, reference_ah=5.0, start_reference_ah=5.0,
        volume_m3=100, elapsed_min=5, connected=True, connection_strength=1.0,
    )
    out = passive_ventilation.evaluate_passive_ventilation(samples=[{"bad": 1}], **common)
    assert out["reason"] == "too_few_samples"

    unstable = passive_ventilation.evaluate_passive_ventilation(
        samples=[
            {"elapsed_min": 1, "ah": 9.7},
            {"elapsed_min": 2, "ah": 9.95},
            {"elapsed_min": 3, "ah": 9.65},
            {"elapsed_min": 4, "ah": 9.9},
        ], **common
    )
    assert unstable["reason"] == "trend_not_stable"

    low_conf = passive_ventilation.evaluate_passive_ventilation(
        start_ah=10.0, current_ah=9.94, reference_ah=5.0, start_reference_ah=5.0,
        volume_m3=100, elapsed_min=4, connected=True, connection_strength=0.45,
        samples=[{"elapsed_min": 2, "ah": 9.97}],
    )
    assert low_conf["reason"] == "confidence_too_low"
    assert low_conf["confidence"] < 45


def test_personal_context_invalid_profiles_unknown_state_and_wording_branches():
    assert personal_context._resident_profiles("[]") == {}
    parsed = personal_context._resident_profiles({
        "bad": {"name": "X"},
        "adult:0": "bad",
        "adult:1": {"name": "Paul", "thermal_preference": "boiling"},
    })
    assert parsed["adult:1"]["thermal_preference"] == "inherit"

    class States:
        def get(self, entity_id):
            return "mystery"

    ctx_unknown = personal_context.build_resident_context(
        {"adult_occupants": 1, "adult_resident_names": "Paul", "adult_presence_entities": ["person.paul"]},
        States(),
    )
    assert ctx_unknown["residents"][0]["presence"] == "unknown"

    base_room = _room(
        key="office", name="Büro", behaviour_recommendation_opportunities=10,
        behaviour_recommendation_followed=8,
    )
    resident = {
        "configured_names": 1,
        "direct_address_name": "Paul",
        "named_adults_home": ["Paul"],
        "residents": [{"name": "Paul", "role": "adult", "room_keys": ["office"], "thermal_preference": "warm"}],
    }
    rec = {"kind": "ventilate", "room_keys": ["office"], "summary": "Lüften.", "reasons": [], "expected_temperature_change_c": -0.3}
    morning = personal_context.personalise_recommendation(rec, {"office": base_room}, _options(), now=datetime(2026,9,15,8), resident_context=resident)
    assert "übliche Morgenlüftung" in morning["summary"]

    # Directly addressed resident without exactly one assigned selected room: evening/day branches.
    resident_many = dict(resident)
    resident_many["residents"] = [{"name": "Paul", "role": "adult", "room_keys": [], "thermal_preference": "inherit"}]
    evening = personal_context.personalise_recommendation(rec, {"office": base_room}, _options(), now=datetime(2026,9,15,19), resident_context=resident_many)
    assert "vor der Nacht" in evening["summary"]
    day = personal_context.personalise_recommendation(rec, {"office": base_room}, _options(personal_priority="climate"), now=datetime(2026,9,15,12), resident_context=resident_many)
    assert "guter Zeitpunkt" in day["summary"]
    assert any("Raumklima" in x for x in day["reasons"])

    wait = personal_context.personalise_recommendation(
        {"kind": "wait", "room_keys": [], "summary": "Warten.", "reasons": []}, {},
        _options(thermal_preference="warm"), now=datetime(2026,9,15,12), resident_context={},
    )
    assert "Wärmeverlust" in wait["summary"]


def test_planner_numeric_co2_pressure_and_after_night_selection(monkeypatch):
    class BadFloat:
        def __float__(self):
            raise ValueError
    assert planner._f(BadFloat(), 7) == 7
    assert planner._pressure(_room(co2=1500, co2_available=True), _options()) >= 30

    monkeypatch.setattr(planner, "project_generation_ml", lambda *a, **k: (0.0, 0.0))
    rooms = {"r": _room(potential_ml=0, realistic_potential_ml=0, delta_g_m3=0, humidity=50, surface_rh=60, co2=None, co2_available=False)}
    plan = planner.build_multi_hour_plan(
        rooms, _options(min_potential_total_ml=500), datetime(2026,9,15,9),
        night_forecast_ml=1, night_confidence=80,
    )
    assert plan["selected_option_id"] == "after_night"
    assert "Nacht" in plan["summary"]


def test_post_stabilization_timezone_mix_and_continued_drying():
    aware_start = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)
    naive_now = datetime(2026, 9, 15, 8, 5)
    assert post_stabilization._elapsed_minutes(aware_start, naive_now) == 5

    room = {
        "post_close_started_at": aware_start.isoformat(),
        "post_close_ah": 10.0,
        "post_close_temp_c": 20.0,
        "post_close_volume_m3": 100,
        "post_close_removed_ml": 100,
        "post_close_start_frame_quality": "excellent",
        "post_close_contaminated": False,
        "post_close_samples": [{}, {}],
    }
    out = post_stabilization._outcome(
        room, now=aware_start + timedelta(minutes=10), current_ah=9.8,
        current_temp_c=20.2, status="complete", reason="test", frame_quality="excellent",
    )
    assert out["interpretation"] == "continued_drying"
    assert out["continued_drying_ml"] == 20.0


def test_presence_unknown_zero_household_and_pet_soft_sensor():
    assert presence._state_kind("unknown") == "unknown"
    empty = presence.resolve_occupancy({}, lambda _: None)
    assert empty["presence_confidence"] == 100

    opts = {
        "adult_occupants": 1,
        "adult_presence_entities": ["person.p"],
        "pets_in_household": True,
        "presence_sensor_entities": ["binary_sensor.motion"],
        "pet_safe_presence_entities": [],
    }
    states = {"person.p": "away", "binary_sensor.motion": "on"}
    out = presence.resolve_occupancy(opts, lambda entity: states.get(entity))
    assert out["soft_presence_score"] == pytest.approx(0.12)


def test_recommendation_problem_airflow_openings_and_wait_explanations():
    opts = _options()
    problem, urgent, reasons, score = recommendation._problem(
        _room(humidity=70, surface_rh=95, co2=1500, humidity_trend_pct_h=4), opts
    )
    assert problem and urgent
    assert any("Schimmel" in x for x in reasons)
    assert any("CO₂" in x for x in reasons)
    assert any("steigt schnell" in x for x in reasons)

    warning = recommendation._problem(_room(humidity=60, surface_rh=82, co2=1100), opts)
    assert any("erhöhtes Schimmelrisiko" in x for x in warning[2])
    assert any("CO₂" in x for x in warning[2])
    fallback_mould = recommendation._problem(_room(humidity=60, surface_rh=75, mould_level="Elevated", co2=700), opts)
    assert any("auffällig" in x for x in fallback_mould[2])

    high_air = recommendation._candidate(_room(airflow_factor=1.2), opts, 100)
    low_air = recommendation._candidate(_room(airflow_factor=0.8), opts, 100)
    assert any("unterstützt" in x for x in high_air.reasons)
    assert any("bremst" in x for x in low_air.reasons)

    # Selected ventilation exposes configured opening labels and airflow explanation.
    selected = _room(
        key="a", name="Arbeitszimmer", airflow_factor=1.2, contact_entities=["binary_sensor.fenster_links"],
        potential_ml=200, realistic_potential_ml=200, action="Ventilate", floor="ground_floor",
    )
    rec = recommendation.build_recommendation(
        {"a": selected}, opts, threshold_ml=100, total_potential_ml=200,
        recommended_duration_min=5,
    )
    assert "fenster links" in rec["instruction"]
    assert any("Windrichtung" in x for x in rec["reasons"])

    # Urgent non-candidate problem is skipped by the deferred non-urgent loop and
    # later explained by the blocked-problem fallback.
    urgent_wait = _room(
        key="u", name="Urgent", humidity=75, surface_rh=95, action="Wait",
        delta_g_m3=0.2, potential_ml=0, realistic_potential_ml=0,
    )
    blocked = recommendation.build_recommendation(
        {"u": urgent_wait}, opts, threshold_ml=500, total_potential_ml=0,
        recommended_duration_min=5,
    )
    assert blocked["kind"] == "wait"

    # Non-urgent candidate with positive room potential but an explicitly bad
    # house-wide effect is deferred and gets the house-physics explanation.
    deferred = _room(
        key="d", name="Deferred", humidity=69, surface_rh=75, action="Ventilate",
        delta_g_m3=1.0, potential_ml=80, realistic_potential_ml=80,
    )
    waited = recommendation.build_recommendation(
        {"d": deferred}, opts, threshold_ml=500, total_potential_ml=-50,
        recommended_duration_min=5,
    )
    assert waited["kind"] == "wait"
    assert any("Hausweit" in x for x in waited["reasons"])

    # Positive but too-small drying gradient reaches the specific blocked reason.
    small_delta = _room(
        key="s", name="Small", humidity=70, surface_rh=75, action="Wait",
        delta_g_m3=0.2, potential_ml=0, realistic_potential_ml=0,
    )
    waited2 = recommendation.build_recommendation(
        {"s": small_delta}, opts, threshold_ml=500, total_potential_ml=0,
        recommended_duration_min=5,
    )
    assert any("zu klein" in x for x in waited2["reasons"])


def test_robustness_out_of_range_result_is_neutralised():
    room = {"session_result_base_ml": 0, "session_result_ml": 1_000_001}
    repaired = robustness.sanitize_runtime_session(room)
    assert room["session_result_ml"] == 0.0
    assert "session_result_ml" in repaired
