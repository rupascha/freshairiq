from datetime import date, timedelta

from custom_components.freshairiq.learning_components import build_learning_components_status
from custom_components.freshairiq.seasonality import learn_seasonal_source
from custom_components.freshairiq.routines import learn_source_pattern


def _days(start: date, end: date):
    out=[]
    cur=start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def test_raw_night_samples_do_not_create_fake_nights():
    status = build_learning_components_status([], {"night_model_samples": 500})
    night = next(x for x in status["components"] if x["key"] == "night_model")
    assert night["samples"] == 0
    assert night["maturity_percent"] == 0
    assert night["status"] in {"Grundschätzung", "Grundmodell"}


def test_night_maturity_counts_unique_nights_only():
    nights=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(7)]
    status = build_learning_components_status([], {"night_model_samples": 122, "night_observed_dates": nights})
    night = next(x for x in status["components"] if x["key"] == "night_model")
    assert night["samples"] == 7
    assert night["maturity_percent"] < 6
    assert "7 unterschiedliche Nächte" in night["evidence_text"]


def test_seasonality_requires_four_fully_traversed_seasons_and_year_span():
    room={"calculation_enabled": True, "seasonal_samples": 9000, "seasonal_observation_days": {
        "2025:spring": _days(date(2025,3,1), date(2025,5,31)),
        "2025:summer": _days(date(2025,6,1), date(2025,8,31)),
        "2025:autumn": _days(date(2025,9,1), date(2025,11,30)),
        "2025:winter": _days(date(2025,12,1), date(2026,2,28)),
    }}
    status=build_learning_components_status({"r": room}, {})
    season=next(x for x in status["components"] if x["key"] == "seasonality")
    assert season["samples"] == 4
    assert season["calendar_span_days"] >= 365
    assert season["maturity_percent"] == 100
    assert season["status"] == "Auf deine Bedürfnisse optimiert"
    assert all(x["optimized"] for x in season["season_breakdown"])


def test_partial_season_can_never_be_optimized_by_sample_volume():
    room={"calculation_enabled": True, "seasonal_samples": 100000, "seasonal_observation_days": {
        "2026:autumn": _days(date(2026,9,10), date(2026,11,30)),
    }}
    status=build_learning_components_status({"r": room}, {})
    season=next(x for x in status["components"] if x["key"] == "seasonality")
    assert season["samples"] == 0
    assert season["maturity_percent"] == 0
    assert season["status"] != "Auf deine Bedürfnisse optimiert"


def test_routine_repeated_samples_need_distinct_days():
    room={"calculation_enabled": True, "routine_source_samples": 8000, "routine_maturity": 100, "routine_observation_dates": ["2026-09-16"]}
    status=build_learning_components_status({"r": room}, {})
    routine=next(x for x in status["components"] if x["key"] == "routines")
    assert routine["samples"] == 1
    assert routine["maturity_percent"] < 2
