"""Behavioural boundary tests for the house-level decision rules (0.26.3.2).

Each test pins a rule at its threshold: just below, exactly at and just above.
Mutation testing showed that the coordinator golden master does not notice a
shifted threshold when the scenario data never reaches it; these tests do.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.freshairiq.house_decision import (
    build_night_strategy,
    floor_ventilation_decision,
    ventilation_threshold_decision,
)

TZ = ZoneInfo("Europe/Berlin")


# --------------------------------------------------------------------- threshold
def _threshold(**overrides):
    kwargs = dict(
        expected_daily_generation=2000.0, now=datetime(2026, 1, 15, 12, 0, tzinfo=TZ), options={},
        outdoor_t=5.0, pollen=0.0, threshold_mode="adaptive_home_size", total_water=10000.0,
        valid=[{"temperature": 21.0, "volume_m3": 40.0, "surface_rh": 60.0}],
    )
    kwargs.update(overrides)
    pollen_blocked, reason, threshold = ventilation_threshold_decision(**kwargs)
    return pollen_blocked, reason, threshold


def test_fixed_threshold_uses_configured_ml_with_500_default():
    assert _threshold(threshold_mode="fixed_ml")[1:] == ("fixed_ml", 500.0)
    assert _threshold(threshold_mode="fixed_ml", options={"min_potential_total_ml": 320})[2] == 320.0


def test_percent_threshold_is_share_of_water_in_air_with_10_percent_default():
    assert _threshold(threshold_mode="percent_total_water", total_water=2000.0)[1:] == ("percent_total_water", 200.0)
    assert _threshold(threshold_mode="percent_total_water", total_water=2000.0,
                      options={"min_potential_percent_total_water": 5})[2] == 100.0


@pytest.mark.parametrize("expected_daily, threshold", [
    (2000.0, 600.0),    # quarter of a day (500) is raised to the 6 % floor
    (3200.0, 800.0),    # inside the 6-12 % corridor: a quarter of the daily load
    (8000.0, 1200.0),   # capped at 12 % of the water in the air
])
def test_adaptive_threshold_aims_for_four_airings_a_day_within_6_to_12_percent(expected_daily, threshold):
    assert _threshold(expected_daily_generation=expected_daily) == (False, "adaptive_home_size", threshold)


def test_adaptive_threshold_without_water_content_falls_back_to_daily_quarter():
    assert _threshold(total_water=0.0, expected_daily_generation=2000.0)[2] == 500.0
    # Any positive water content keeps the 6-12 % corridor.
    assert _threshold(total_water=0.4, expected_daily_generation=2000.0)[2] == pytest.approx(0.048)


@pytest.mark.parametrize("month, hour, outdoor, cool", [
    (6, 8, 18.0, True),    # summer morning, 3 K cooler outside
    (6, 9, 18.0, False),   # 09:00 is no longer "morning"
    (6, 18, 18.0, False),  # 18:59 is not yet "evening"
    (6, 19, 18.0, True),   # from 19:00
    (4, 8, 18.0, False),   # April is outside the warm season
    (5, 8, 18.0, True),    # May is inside
    (8, 8, 18.0, True),    # August is inside
    (9, 8, 18.0, True),    # September is inside
    (10, 8, 18.0, False),  # October is outside
    (6, 8, 19.0, True),    # exactly 2.0 K cooler counts
    (6, 8, 19.01, False),  # less than 2.0 K does not
    (6, 8, None, False),   # no outdoor temperature, no cool window
])
def test_warm_season_cool_window_lowers_the_threshold_by_a_quarter(month, hour, outdoor, cool):
    pollen_blocked, reason, threshold = _threshold(now=datetime(2026, month, 10, hour, 59 if hour == 18 else 0, tzinfo=TZ),
                                                   outdoor_t=outdoor, valid=[{"temperature": 21.0, "volume_m3": 40.0}])
    assert reason == ("adaptive_home_size_cool_window" if cool else "adaptive_home_size")
    assert threshold == (450.0 if cool else 600.0)


def test_cool_window_uses_volume_weighted_indoor_temperature():
    # Weighted: (22*20 + 18*60) / 80 = 19.0 °C -> outdoor 17.5 is only 1.5 K cooler.
    # An unweighted mean (20.0 °C) would wrongly open the cool window.
    rooms = [{"temperature": 22.0, "volume_m3": 20.0}, {"temperature": 18.0, "volume_m3": 60.0}]
    assert _threshold(now=datetime(2026, 7, 1, 7, 0, tzinfo=TZ), outdoor_t=17.5, valid=rooms)[1] == "adaptive_home_size"
    assert _threshold(now=datetime(2026, 7, 1, 7, 0, tzinfo=TZ), outdoor_t=17.0, valid=rooms)[1] == "adaptive_home_size_cool_window"


@pytest.mark.parametrize("options, pollen, blocked", [
    ({}, 9.0, False),                                                     # pollen check is opt-in
    ({"pollen_enabled": True}, 4.0, False),                               # exactly the limit is allowed
    ({"pollen_enabled": True}, 4.01, True),                               # above the default limit of 4
    ({"pollen_enabled": True, "pollen_strict_veto": False}, 9.0, False),  # advisory mode never blocks
    ({"pollen_enabled": True, "pollen_max": 6}, 6.0, False),
    ({"pollen_enabled": True, "pollen_max": 6}, 6.5, True),
])
def test_pollen_veto(options, pollen, blocked):
    assert _threshold(options=options, pollen=pollen)[0] is blocked


@pytest.mark.parametrize("room, blocked", [
    ({"temperature": 21, "volume_m3": 40, "surface_rh": 89.9}, True),
    ({"temperature": 21, "volume_m3": 40, "surface_rh": 90.0}, False),   # critical mould risk overrides pollen
    ({"temperature": 21, "volume_m3": 40, "co2_available": True, "co2": 1399}, True),
    ({"temperature": 21, "volume_m3": 40, "co2_available": True, "co2": 1400}, False),  # critical CO2 overrides pollen
    ({"temperature": 21, "volume_m3": 40, "co2_available": False, "co2": 5000}, True),  # CO2 without a sensor is ignored
    ({"temperature": 21, "volume_m3": 40, "co2_available": True, "co2": None}, True),
])
def test_critical_indoor_air_overrides_the_pollen_veto(room, blocked):
    assert _threshold(options={"pollen_enabled": True}, pollen=5.0, valid=[room])[0] is blocked


# ------------------------------------------------------------------------- floor
def _room(key, floor="ground_floor", **extra):
    room = {"key": key, "name": key.title(), "floor": floor, "volume_m3": 30.0,
            "forecast_5_min_net_moisture_change_ml": 20.0, "forecast_5_min_temperature_change_c": -0.1,
            "close_decision_ready": True, "action": "Continue ventilating"}
    room.update(extra)
    return room


def _floor(active, valid, house_mode=False, options=None, recommendation=None):
    rec = {} if recommendation is None else recommendation
    name, mode = floor_ventilation_decision(
        active=active, cross=False, forecast_confidence=70, forecast_cost=0.12,
        house_ventilation_mode=house_mode, intelligent_recommendation=rec,
        night_strategy={}, options=options or {}, valid=valid,
    )
    return name, mode, rec


@pytest.mark.parametrize("active_n, total_n, floor_mode", [
    (1, 1, False),  # a single open room is never a floor ventilation
    (2, 4, True),   # two rooms covering half of the floor
    (2, 5, False),  # two rooms covering less than half
    (3, 7, True),   # three active rooms always count
])
def test_floor_mode_needs_two_rooms_covering_half_or_three_rooms(active_n, total_n, floor_mode):
    valid = [_room(f"r{i}") for i in range(total_n)]
    name, mode, rec = _floor(valid[:active_n], valid)
    assert mode is floor_mode
    assert rec["presentation_scope"] == ("floor" if floor_mode else "rooms")
    if floor_mode:
        assert name == "Erdgeschoss" and rec["presentation_floor"] == "Erdgeschoss"
        assert rec["decision_brain"]["version"] == "v1-floor"


def test_floor_mode_picks_the_floor_with_most_active_rooms_and_names_it():
    valid = [_room("a", "upper_floor"), _room("b", "upper_floor"), _room("c", "ground_floor"), _room("d", "loft")]
    name, mode, rec = _floor(valid[:3], valid)
    assert (name, mode) == ("Obergeschoss", True)
    assert rec["room_keys"] == ["a", "b"]
    assert _floor([], [_room("x", "loft")])[0] == "Stockwerk"  # nothing active: no floor chosen
    assert _floor([_room("x", None)], [_room("x", None)])[0] == "Unzugeordnet"


def test_house_mode_takes_precedence_over_floor_mode():
    valid = [_room(f"r{i}") for i in range(3)]
    name, mode, rec = _floor(valid, valid, house_mode=True)
    assert mode is False and rec["presentation_scope"] == "house"
    assert rec["decision_brain"]["version"] == "v1-house"


@pytest.mark.parametrize("house_mode", [True, False])
@pytest.mark.parametrize("net_total, expected_kind", [
    (49.9, "close"),     # below 25 ml * sqrt(4 rooms) = 50 ml
    (50.0, "continue"),  # exactly the shared threshold keeps ventilating
])
def test_aggregate_low_return_threshold_scales_with_square_root_of_rooms(house_mode, net_total, expected_kind):
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=net_total / 4) for i in range(4)]
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode)
    assert rec["kind"] == expected_kind
    if house_mode:
        assert rec["house_decision_threshold_ml"] == 50


@pytest.mark.parametrize("house_mode", [True, False])
@pytest.mark.parametrize("cooling_c, profile, expected_kind", [
    (0.59, "comfort", "continue"),        # below the default 0.6 K limit
    (0.60, "comfort", "close"),           # at the limit with poor efficiency
    (0.60, "summer_cooling", "continue"), # cooling is the goal in summer mode
])
def test_aggregate_thermal_protection_closes_on_strong_cooling_with_poor_efficiency(house_mode, cooling_c, profile, expected_kind):
    # 3 rooms x 15 ml = 45 ml, above the return threshold 20 ml * sqrt(3) = 34.6 ml.
    # At 0.6 K cooling the efficiency is 45 / (0.6 * 10) = 7.5 ml per 0.1 K, below the default 8.
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=15.0, forecast_5_min_temperature_change_c=-cooling_c) for i in range(3)]
    options = {"operating_profile": profile, "min_return_next_5_min_ml": 20}
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode, options=options)
    assert rec["kind"] == expected_kind


@pytest.mark.parametrize("house_mode", [True, False])
def test_aggregate_close_waits_until_every_room_released_its_gate(house_mode):
    rooms = [_room("a", forecast_5_min_net_moisture_change_ml=0.0), _room("b", forecast_5_min_net_moisture_change_ml=0.0, close_decision_ready=False)]
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode, recommendation={"duration_min": 0})
    assert rec["kind"] == "continue"
    assert any("1/2" in reason for reason in rec["reasons"])
    assert rec["duration_min"] is None  # no fake "0 min left" while the gate is closed


@pytest.mark.parametrize("house_mode", [True, False])
def test_aggregate_reports_signed_moisture_effect(house_mode):
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=-10.0) for i in range(2)]
    _, _, rec = _floor(rooms, rooms + [_room("x")], house_mode=house_mode)
    assert rec["kind"] == "close"  # moisture is coming in: -20 ml is below any positive threshold
    expected = "20 ml Feuchtezunahme" if house_mode else "-20 ml"
    assert any(expected in reason for reason in rec["reasons"]), rec["reasons"]


def test_house_efficiency_ignores_negligible_cooling():
    # <= 0.05 K cooling never counts as thermally bad, regardless of the moisture effect.
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=30.0, forecast_5_min_temperature_change_c=-0.05) for i in range(2)]
    _, _, rec = _floor(rooms, rooms, house_mode=True, options={"max_temp_loss_next_5_min_c": 0.0})
    assert rec["kind"] == "continue"


# ------------------------------------------------------------------------- night
def _night(**overrides):
    kwargs = dict(
        avg_indoor_ah=9.0, first_rain_dt=None, max_night_temp_loss_c=1.5, minutes_until_rain=None,
        night_ah_delta=-0.2, night_avg_ah=8.8, night_avg_temp=8.0, night_confidence=80,
        night_energy_cost=0.4, night_energy_kwh=1.2, night_forecast=150, night_forecast_closed=120,
        night_forecast_with_selected=-60, night_hours=8.0, night_max_rh=88.0, night_min_temp=5.0,
        night_rain_expected=False, night_rain_mm=0.0, night_rain_prob=0.0, night_strategy_relevant=True,
        night_temperature_change_c=-0.8, night_weather_available=True, open_rooms=[], pre_vent_effect=0.0,
        pre_vent_source_ah=None, prebed_minutes=11, rain_start_label=None, selected_night=[{"room": {}}],
        selected_night_names=["Wohnküche", "Flur EG"], selected_weather_effect=-180.0, thermal_ok=True,
    )
    kwargs.update(overrides)
    return build_night_strategy(**kwargs)


@pytest.mark.parametrize("overrides", [
    {"night_strategy_relevant": False},
    {"night_weather_available": False},
    {"night_ah_delta": None},
])
def test_night_strategy_only_decides_with_relevance_weather_and_humidity_delta(overrides):
    assert _night(**{"night_ah_delta": -2.0, **overrides})["action"] == "monitor"


def test_night_confidence_is_capped_without_weather_forecast():
    assert _night(night_weather_available=False, night_confidence=90)["confidence"] == 65
    assert _night(night_confidence=99)["confidence"] == 95


@pytest.mark.parametrize("delta, action", [
    (-0.59, "close"),  # rain, outdoor air not clearly drier -> close
    (-0.60, "close"),  # drier, but no dry window before the rain is known -> close ("zu knapp")
])
def test_rain_closes_windows_unless_outdoor_air_is_clearly_drier(delta, action):
    strategy = _night(night_rain_expected=True, night_ah_delta=delta, night_rain_prob=70, open_rooms=["Bad"])
    assert strategy["action"] == action
    assert strategy["instruction"] in ("Alle geöffneten Fenster vor der Nacht schließen", "Fenster über Nacht geschlossen lassen")


@pytest.mark.parametrize("minutes, source_ah, action", [
    (16, 8.4, "pre_ventilate"),  # 11 min airing + 5 min reserve, 0.6 g/m³ drier
    (15, 8.4, "close"),          # one minute too short
    (16, 8.41, "close"),         # not 0.6 g/m³ drier
    (None, 8.4, "close"),        # rain onset unknown
])
def test_pre_ventilating_before_rain_needs_a_dry_and_long_enough_window(minutes, source_ah, action):
    rain = datetime(2026, 10, 7, 23, 0, tzinfo=TZ)
    strategy = _night(night_rain_expected=True, night_ah_delta=-1.0, minutes_until_rain=minutes, pre_vent_source_ah=source_ah,
                      first_rain_dt=rain, rain_start_label="23:00", pre_vent_effect=-81.4)
    assert strategy["action"] == action
    assert strategy["rain_start"] == rain.isoformat()
    if action == "pre_ventilate":
        assert strategy["instruction"] == "Wohnküche + Flur EG bis spätestens 23:00 Uhr etwa 11 Minuten stoßlüften und danach schließen"
        assert strategy["forecast_with_strategy_ml"] == round(120 - 81.4)
        assert strategy["strategy_moisture_effect_ml"] == -81


def test_pre_ventilation_without_rain_label_names_the_rain_phase_generically():
    strategy = _night(night_rain_expected=True, night_ah_delta=-1.0, minutes_until_rain=40, pre_vent_source_ah=8.0, night_rain_prob=60)
    assert strategy["instruction"].endswith("vor der Regenphase etwa 11 Minuten stoßlüften und danach schließen")


@pytest.mark.parametrize("delta, thermal_ok, selected, action", [
    (-0.6, True, True, "open_selected"),
    (-0.59, True, True, "closed_monitor"),
    (-0.6, False, True, "pre_ventilate"),
    (-0.6, True, False, "closed_monitor"),
    (0.39, True, True, "closed_monitor"),
    (0.4, True, True, "close"),          # humid night air stays outside
])
def test_dry_night_without_rain(delta, thermal_ok, selected, action):
    strategy = _night(night_ah_delta=delta, thermal_ok=thermal_ok, selected_night=[{"room": {}}] if selected else [],
                      selected_night_names=["Schlafzimmer"] if selected else [])
    assert strategy["action"] == action


def test_open_selected_reports_effect_and_rooms():
    strategy = _night(night_ah_delta=-1.2)
    assert strategy["instruction"] == "Wohnküche + Flur EG über Nacht nur teilweise geöffnet lassen"
    assert strategy["forecast_with_strategy_ml"] == -60 and strategy["strategy_moisture_effect_ml"] == -180


@pytest.mark.parametrize("effect, expected", [(-1.0, None), (-1.01, 119), (-40.0, 80)])
def test_pre_ventilation_effect_is_only_shown_when_meaningful(effect, expected):
    strategy = _night(night_ah_delta=-1.0, thermal_ok=False, pre_vent_effect=effect)
    assert strategy["action"] == "pre_ventilate"
    assert strategy["forecast_with_strategy_ml"] == expected


def test_humid_night_reports_avoided_moisture_when_windows_are_open():
    strategy = _night(night_ah_delta=0.8, open_rooms=["Bad"])
    assert strategy["strategy_moisture_effect_ml"] == 120 - 150
    assert _night(night_ah_delta=0.8)["strategy_moisture_effect_ml"] == 0


def test_neutral_night_without_minimum_temperature_still_explains():
    strategy = _night(night_ah_delta=0.0, night_min_temp=None, night_avg_ah=None, night_avg_temp=None,
                      night_temperature_change_c=None, night_max_rh=None)
    assert strategy["action"] == "closed_monitor"
    assert strategy["reasons"][1] == "Temperaturprognose wird weiter beobachtet"
    assert strategy["min_temperature_c"] is None and strategy["outside_ah_g_m3"] is None


# ---------------------------------------------------- aggregate edge boundaries
@pytest.mark.parametrize("house_mode", [True, False])
@pytest.mark.parametrize("net_per_room, expected_kind", [
    (16.0, "continue"),  # 48 ml / (0.6 K * 10) = exactly 8.0 ml per 0.1 K: still efficient enough
    (15.9, "close"),     # 47.7 ml / 6 = 7.95: inefficient at 0.6 K cooling
])
def test_thermal_efficiency_limit_is_eight_ml_per_tenth_kelvin(house_mode, net_per_room, expected_kind):
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=net_per_room, forecast_5_min_temperature_change_c=-0.6) for i in range(3)]
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode, options={"min_return_next_5_min_ml": 20})
    assert rec["kind"] == expected_kind


@pytest.mark.parametrize("house_mode", [True, False])
@pytest.mark.parametrize("cooling_c, expected_kind", [
    (0.05, "continue"),   # up to 0.05 K counts as no cooling at all
    (0.051, "close"),     # above it the (here very poor) efficiency applies
])
def test_negligible_cooling_limit(house_mode, cooling_c, expected_kind):
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=0.1, forecast_5_min_temperature_change_c=-cooling_c) for i in range(2)]
    options = {"min_return_next_5_min_ml": 0, "max_temp_loss_next_5_min_c": 0.0}  # isolate the thermal rule
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode, options=options)
    assert rec["kind"] == expected_kind


@pytest.mark.parametrize("house_mode", [True, False])
def test_legacy_forecast_field_is_used_when_net_effect_is_missing(house_mode):
    rooms = [_room(f"r{i}") for i in range(2)]
    for room in rooms:
        del room["forecast_5_min_net_moisture_change_ml"]
        room["forecast_5_min_moisture_effect_ml"] = 40.0
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode)
    assert rec["kind"] == "continue"  # 80 ml > 25 * sqrt(2) = 35.4 ml


def test_rooms_without_valid_measurements_never_form_a_floor_ventilation():
    active = [_room(f"r{i}") for i in range(3)]
    name, mode, rec = _floor(active, valid=[])
    assert mode is False and rec["presentation_scope"] == "rooms"


@pytest.mark.parametrize("house_mode, min_return, kind", [(True, 25, "close"), (True, 0, "continue")])
def test_zero_net_effect_is_reported_as_no_removal_not_as_gain(house_mode, min_return, kind):
    rooms = [_room(f"r{i}", forecast_5_min_net_moisture_change_ml=0.0) for i in range(2)]
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode, options={"min_return_next_5_min_ml": min_return})
    assert rec["kind"] == kind
    assert any("0 ml Feuchteabbau" in reason for reason in rec["reasons"]), rec["reasons"]


@pytest.mark.parametrize("house_mode", [True, False])
def test_aggregate_brain_offers_no_alternative_options(house_mode):
    rooms = [_room(f"r{i}") for i in range(2)]
    _, _, rec = _floor(rooms, rooms, house_mode=house_mode)
    brain = rec["decision_brain"]
    assert (brain["short_term_options"], brain["long_term_options"], brain["alternative"]) == (0, 0, None)


# ----------------------------------------------------- night: which rule fired
@pytest.mark.parametrize("delta, headline", [
    (-0.59, "Heute Nacht Fenster geschlossen halten"),       # rain + not clearly drier
    (-0.60, "Trockene Luft vor dem Regen gezielt nutzen"),   # rain + drier + dry window
])
def test_rain_rule_switches_to_pre_ventilation_exactly_at_minus_0_6(delta, headline):
    strategy = _night(night_rain_expected=True, night_ah_delta=delta, minutes_until_rain=60, pre_vent_source_ah=8.0,
                      rain_start_label="23:00", pre_vent_effect=-50.0)
    assert strategy["headline"] == headline


@pytest.mark.parametrize("delta, headline", [
    (-0.60, "Trockene Nachtluft erkannt, aber kein Fenster sicher auswählbar"),
    (-0.59, "Für die Nacht ist kein Dauerlüften nötig"),
])
def test_dry_night_without_selectable_room_switches_exactly_at_minus_0_6(delta, headline):
    strategy = _night(night_ah_delta=delta, selected_night=[], selected_night_names=[])
    assert strategy["action"] == "closed_monitor" and strategy["headline"] == headline


@pytest.mark.parametrize("effect, shown", [(-1.0, None), (-1.01, -1), (-30.4, -30)])
def test_thermal_pre_ventilation_reports_effect_only_beyond_one_ml(effect, shown):
    strategy = _night(night_ah_delta=-1.0, thermal_ok=False, pre_vent_effect=effect)
    assert strategy["strategy_moisture_effect_ml"] == shown


def test_neutral_night_reports_no_strategy_effect():
    strategy = _night(night_ah_delta=0.1)
    assert (strategy["forecast_with_strategy_ml"], strategy["strategy_moisture_effect_ml"]) == (120, 0)


# ------------------------------------------------------------ fallback status
from custom_components.freshairiq.house_decision import house_status_fallback  # noqa: E402


def _status(**overrides):
    kwargs = dict(actionable_potential=100.0, active=[], bad=[], close=[], cooling=[], options={},
                  pollen_blocked=False, sensor_recovery_grace=False, valid=[], ventilation_threshold=500.0)
    kwargs.update(overrides)
    return house_status_fallback(**kwargs)


CRITICAL = {"ventilation_candidate": True, "surface_rh": 91.0}


@pytest.mark.parametrize("overrides, expected", [
    ({"bad": ["x"], "sensor_recovery_grace": True, "close": ["y"]}, "sensor_recovering"),
    ({"bad": ["x"], "close": ["y"]}, "sensor_error"),
    ({"close": ["y"], "active": ["z"]}, "close_windows"),
    ({"active": ["z"], "valid": [CRITICAL]}, "ventilation_running"),
    ({"valid": [CRITICAL], "cooling": ["c"]}, "ventilate"),  # hotfix 0.18.24: critical air before cooling
    ({"cooling": ["c"], "pollen_blocked": True, "actionable_potential": 900.0}, "cooling_recommended"),
    ({"pollen_blocked": True, "actionable_potential": 500.0}, "pollen_warning"),
    ({"pollen_blocked": True, "actionable_potential": 499.9}, "okay"),
    ({"actionable_potential": 500.0}, "ventilate"),
    ({"actionable_potential": 499.9}, "okay"),
])
def test_fallback_status_priority(overrides, expected):
    assert _status(**overrides) == expected


@pytest.mark.parametrize("room, urgent", [
    ({"ventilation_candidate": True, "surface_rh": 90.0}, True),
    ({"ventilation_candidate": True, "surface_rh": 89.9}, False),
    ({"ventilation_candidate": False, "surface_rh": 99.0}, False),  # cannot be aired: not urgent for the house
    ({"ventilation_candidate": True, "co2_available": True, "co2": 1400}, True),
    ({"ventilation_candidate": True, "co2_available": True, "co2": 1399}, False),
    ({"ventilation_candidate": True, "co2_available": False, "co2": 3000}, False),
])
def test_critical_indoor_air_only_counts_in_ventilable_rooms(room, urgent):
    assert _status(valid=[room], cooling=["c"]) == ("ventilate" if urgent else "cooling_recommended")
