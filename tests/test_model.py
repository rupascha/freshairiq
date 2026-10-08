from custom_components.freshairiq.model import RoomInput, absolute_humidity, evaluate_room, update_learning
from custom_components.freshairiq.const import DEFAULT_OPTIONS


def test_absolute_humidity_reasonable():
    assert 8.5 < absolute_humidity(20, 50) < 8.7


def test_room_recommends_ventilation():
    room = RoomInput("living", "Living room", 22, 70, 10, 60, 80, False, 0)
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    assert result.data_quality == "ok"
    assert result.action == "Ventilate"
    assert result.potential_ml > 100
    assert result.ventilation_candidate


def test_running_room_can_close_on_low_return():
    room = RoomInput("living", "Living room", 20, 58, 15, 55, 80, True, 600, session_active=True, session_elapsed_min=10, session_start_temp=21, learning_rate=0.03, session_fresh_measurements=2)
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    assert result.action in {"Close", "Continue ventilating"}


def test_pollen_can_veto_nonurgent_ventilation():
    options = {**DEFAULT_OPTIONS, "pollen_enabled": True, "pollen_strict_veto": True, "pollen_max": 4.0}
    room = RoomInput("living", "Living room", 22, 70, 10, 60, 80, False, 0, pollen_index=7.0)
    result = evaluate_room(room, options, False)
    assert result.action == "Do not ventilate"
    assert "Pollen" in result.reason


def test_learning_accepts_valid_sample_beyond_old_45_min_limit():
    rate, samples, diagnosis, valid = update_learning(old_rate=0.03, old_samples=0, elapsed_min=60, start_ah=12, end_ah=10, source_ah=8, learning_enabled=True, max_duration_min=120)
    assert valid
    assert samples == 1
    assert rate > 0
    assert "Learned" in diagnosis


def test_learning_rejects_session_above_configured_maximum():
    rate, samples, diagnosis, valid = update_learning(old_rate=0.03, old_samples=3, elapsed_min=121, start_ah=12, end_ah=10, source_ah=8, learning_enabled=True, max_duration_min=120)
    assert not valid
    assert rate == 0.03
    assert samples == 3
    assert "duration" in diagnosis


def test_learning_rejects_short_session():
    rate, samples, diagnosis, valid = update_learning(old_rate=0.03, old_samples=3, elapsed_min=1, start_ah=12, end_ah=11, source_ah=8, learning_enabled=True, max_duration_min=120)
    assert not valid
    assert rate == 0.03
    assert samples == 3
    assert "duration" in diagnosis


def test_restart_keeps_original_session_baseline():
    """After restart, current measurements remain relative to the original window-open baseline."""
    start_ah = absolute_humidity(22, 65)
    current_ah = absolute_humidity(22, 58)
    room = RoomInput(
        "living", "Living room", 22, 58, 10, 60, 80, True, 600,
        session_active=True, session_elapsed_min=10,
        session_start_ah=start_ah, session_result_base_ml=0,
        session_result_ml=237, session_start_temp=22,
    )
    result = evaluate_room(room, DEFAULT_OPTIONS, False)
    expected = round((start_ah - current_ah) * 80)
    assert result.result_ml == expected


def test_operating_profiles_make_distinct_decisions():
    """The same room must be evaluated differently when profile priorities differ."""
    base = RoomInput("living", "Living room", 25, 55, 20, 60, 80, False, 0)
    comfort = evaluate_room(base, {**DEFAULT_OPTIONS, "operating_profile": "comfort"}, False)
    summer = evaluate_room(base, {**DEFAULT_OPTIONS, "operating_profile": "summer_cooling"}, False)
    dehum = evaluate_room(base, {**DEFAULT_OPTIONS, "operating_profile": "dehumidify"}, False)
    assert summer.cooling_candidate
    assert summer.action in {"Ventilate for cooling", "Ventilate"}
    assert dehum.action != "Ventilate for cooling"
    assert comfort.data_quality == "ok"


def test_summer_cooling_does_not_close_only_because_room_is_cooling():
    options = {
        **DEFAULT_OPTIONS,
        "operating_profile": "summer_cooling",
        "cooling_start_temp_c": 24,
        "cooling_min_outdoor_delta_c": 2,
    }
    room = RoomInput(
        "living", "Living room", 25, 50, 18, 55, 80, True, 600,
        session_active=True, session_elapsed_min=8,
        session_start_temp=27, learning_rate=0.04, session_fresh_measurements=2,
    )
    result = evaluate_room(room, options, False)
    assert result.action == "Continue ventilating"


def test_close_decision_waits_for_two_post_open_measurements():
    options = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20}
    base = dict(
        key="living", name="Living room", temperature=20, humidity=58,
        reference_temperature=15, reference_humidity=55, volume_m3=80,
        contact_open=True, contact_open_seconds=600, session_active=True,
        session_elapsed_min=10, session_start_temp=21, learning_rate=0.03,
    )
    zero = evaluate_room(RoomInput(**base, session_fresh_measurements=0), options, False)
    assert zero.action == "Continue ventilating"
    assert not zero.close_recommended
    assert not zero.close_decision_ready
    assert zero.fresh_measurements == 0

    one = evaluate_room(RoomInput(**base, session_fresh_measurements=1), options, False)
    assert one.action == "Continue ventilating"
    assert not one.close_recommended
    assert not one.close_decision_ready
    assert one.fresh_measurements == 1

    two = evaluate_room(RoomInput(**base, session_fresh_measurements=2), options, False)
    assert two.close_decision_ready
    assert two.fresh_measurements == 2


def test_model_fallback_is_locked_before_15_minutes():
    options = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20}
    room = RoomInput(
        "living", "Living room", 20, 58, 15, 55, 80, True, 899,
        session_active=True, session_elapsed_min=14.983, session_start_temp=21,
        learning_rate=0.03, session_fresh_measurements=0,
    )
    result = evaluate_room(room, options, False)
    assert result.action == "Continue ventilating"
    assert not result.close_recommended
    assert not result.close_decision_ready
    assert not result.close_decision_model_fallback


def test_model_fallback_releases_at_15_minutes_without_auto_close():
    options = {
        **DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20,
        "min_return_next_5_min_ml": 1,
    }
    room = RoomInput(
        "living", "Living room", 23, 70, 8, 45, 80, True, 900,
        session_active=True, session_elapsed_min=15.0, session_start_temp=23,
        learning_rate=0.03, session_fresh_measurements=0,
    )
    result = evaluate_room(room, options, False)
    assert result.close_decision_ready
    assert result.close_decision_model_fallback
    assert result.action == "Continue ventilating"
    assert not result.close_recommended


def test_model_fallback_can_close_after_15_minutes_when_model_requires_it():
    options = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 20}
    room = RoomInput(
        "living", "Living room", 20, 58, 15, 55, 80, True, 1800,
        session_active=True, session_elapsed_min=30, session_start_temp=21,
        learning_rate=0.03, session_fresh_measurements=0,
    )
    result = evaluate_room(room, options, False)
    assert result.close_decision_ready
    assert result.close_decision_model_fallback
    assert result.action == "Close"
    assert result.close_recommended

