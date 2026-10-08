"""Regression tests for FreshAirIQ 0.25.0.7 optional interventions."""
from custom_components.freshairiq.intervention import build_interventions, executable_intervention


def _room(**extra):
    data = {
        "action": "Okay",
        "humidity": 50.0,
        "temperature": 21.0,
        "co2": 700.0,
        "voc": None,
        "pm25": None,
        "illuminance": None,
        "moisture_source_active": False,
        "pollen_blocked": False,
    }
    data.update(extra)
    return data


def _options(**extra):
    data = {
        "start_rh": 62.0,
        "high_rh": 68.0,
        "co2_warn": 1000.0,
        "voc_warn": 600.0,
        "pm25_warn": 15.0,
        "humidify_below_rh": 35.0,
        "shade_above_temp_c": 24.0,
        "shade_min_illuminance_lx": 10000.0,
    }
    data.update(extra)
    return data


def test_no_optional_equipment_keeps_intervention_layer_empty():
    assert build_interventions(room=_room(action="Ventilate"), config={}, options=_options()) == []


def test_moisture_source_prioritises_exhaust():
    rows = build_interventions(
        room=_room(humidity=72, moisture_source_active=True),
        config={"exhaust_fan": "fan.bathroom"},
        options=_options(),
    )
    assert rows[0]["key"] == "extract_moisture"
    assert rows[0]["service"] == "fan.turn_on"
    assert rows[0]["automatic_safe"] is True


def test_pollen_blocked_high_humidity_prefers_dehumidifier():
    rows = build_interventions(
        room=_room(humidity=66, pollen_blocked=True, action="Do not ventilate"),
        config={"dehumidifier": "switch.dehumidifier"},
        options=_options(),
    )
    assert rows[0]["key"] == "dehumidify"
    assert rows[0]["priority"] >= 90


def test_bad_particles_recommend_air_purifier():
    rows = build_interventions(
        room=_room(pm25=40),
        config={"air_purifier": "fan.purifier"},
        options=_options(),
    )
    assert rows[0]["key"] == "purify_air"


def test_hot_bright_room_recommends_all_configured_covers():
    rows = build_interventions(
        room=_room(temperature=27, illuminance=25000),
        config={"covers": ["cover.one", "cover.two"]},
        options=_options(),
    )
    shade = [row for row in rows if row["key"] == "shade"]
    assert {row["entity_id"] for row in shade} == {"cover.one", "cover.two"}
    assert all(row["service"] == "cover.close_cover" for row in shade)


def test_climate_is_recommendation_only_without_invented_hvac_target():
    rows = build_interventions(
        room=_room(temperature=28, action="Do not ventilate"),
        config={"climate": "climate.living_room"},
        options=_options(),
    )
    climate = next(row for row in rows if row["key"] == "climate_cooling")
    assert climate["service"] is None
    assert climate["automatic_safe"] is False


def test_critical_co2_can_use_mechanical_ventilation():
    rows = build_interventions(
        room=_room(co2=1500, action="Ventilate"),
        config={"ventilation_device": "fan.hrv"},
        options=_options(),
    )
    assert rows[0]["key"] == "mechanical_ventilation"
    assert rows[0]["service"] == "fan.turn_on"


def test_executable_intervention_never_returns_recommendation_only_action():
    rows = build_interventions(
        room=_room(temperature=28, action="Do not ventilate"),
        config={"climate": "climate.living_room"},
        options=_options(),
    )
    assert executable_intervention(rows) is None


def test_intervention_numeric_inputs_reject_nan_and_infinity():
    rows = build_interventions(
        room=_room(temperature=float("nan"), humidity=float("inf"), pm25=float("nan")),
        config={
            "covers": "cover.single",
            "dehumidifier": "switch.dehumidifier",
            "air_purifier": "fan.purifier",
        },
        options=_options(),
    )
    assert rows == []


def test_intervention_helpers_handle_single_cover_and_non_turn_on_domains():
    rows = build_interventions(
        room=_room(temperature=28, illuminance=None, humidity=70),
        config={
            "covers": "cover.single",
            "dehumidifier": "climate.not_a_turn_on_domain",
        },
        options=_options(),
    )
    shade = next(row for row in rows if row["key"] == "shade")
    assert shade["entity_id"] == "cover.single"
    dehumidify = next(row for row in rows if row["key"] == "dehumidify")
    assert dehumidify["service"] is None


def test_executable_intervention_key_filters_candidates():
    rows = build_interventions(
        room=_room(humidity=75, moisture_source_active=True),
        config={"exhaust_fan": "fan.exhaust", "dehumidifier": "switch.dry"},
        options=_options(),
    )
    assert executable_intervention(rows, "dehumidify")["entity_id"] == "switch.dry"
    assert executable_intervention(rows, "does_not_exist") is None
