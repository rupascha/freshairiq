"""N2 (0.26.7.1): season model and learning progress – calendar season, observed days and coverage are separate.

The season follows the local calendar month of the Home Assistant time zone (the coordinator passes ``dt_util.now()``):
autumn until 30 November, winter from 1 December. Reaching 60 observation days does not switch or complete a season –
a season is complete only with ≥ 60 distinct days AND observations near its start and its end. Learning goes on after
day 60. Polling on the same day adds no day; different years are never merged into one season.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from custom_components.freshairiq.learning_components import _routine_and_seasonal_parts
from custom_components.freshairiq.seasonality import learn_seasonal_source, season_key, seasonal_context

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.mark.parametrize("when,expected", [
    (datetime(2026, 11, 15, 12, 0, tzinfo=BERLIN), "autumn"),
    (datetime(2026, 11, 30, 23, 59, tzinfo=BERLIN), "autumn"),
    (datetime(2026, 12, 1, 0, 0, tzinfo=BERLIN), "winter"),
    (datetime(2027, 1, 1, 0, 0, tzinfo=BERLIN), "winter"),
    (datetime(2028, 2, 29, 12, 0, tzinfo=BERLIN), "winter"),        # leap day
    (datetime(2027, 2, 28, 23, 59, tzinfo=BERLIN), "winter"),
    (datetime(2027, 3, 1, 0, 0, tzinfo=BERLIN), "spring"),
    (datetime(2027, 3, 28, 3, 30, tzinfo=BERLIN), "spring"),        # DST start
    (datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN), "autumn"),       # DST end
])
def test_season_follows_the_local_calendar(when, expected):
    assert season_key(when) == expected


def test_local_time_not_utc_decides_the_change():
    utc = datetime(2026, 11, 30, 23, 30, tzinfo=timezone.utc)         # still 30 Nov in UTC …
    assert season_key(utc) == "autumn"
    assert season_key(utc.astimezone(BERLIN)) == "winter"              # … but 1 Dec 00:30 in Berlin (what HA passes)


def _learn(room, start: date, days: int, *, per_day: int = 1):
    for i in range(days):
        for k in range(per_day):
            learn_seasonal_source(room, datetime.combine(start + timedelta(days=i), datetime.min.time(), BERLIN) + timedelta(hours=8, minutes=12 * k), 2.0)


def test_polling_on_the_same_day_adds_no_day_and_years_stay_apart():
    room: dict = {}
    _learn(room, date(2026, 11, 30), 1, per_day=50)
    learn_seasonal_source(room, datetime(2026, 12, 1, 8, tzinfo=BERLIN), 2.0)
    learn_seasonal_source(room, datetime(2027, 1, 1, 8, tzinfo=BERLIN), 2.0)
    learn_seasonal_source(room, datetime(2027, 12, 2, 8, tzinfo=BERLIN), 2.0)
    obs = room["seasonal_observation_days"]
    assert obs["2026:autumn"] == ["2026-11-30"]
    assert obs["2026:winter"] == ["2026-12-01", "2027-01-01"]          # one winter spans the turn of the year
    assert obs["2027:winter"] == ["2027-12-02"]                       # the next winter is its own period


def _seasons(room):
    parts = _routine_and_seasonal_parts(n=1, valid=[room])
    breakdown = next(x for x in parts if isinstance(x, list) and x and isinstance(x[0], dict) and "observed_days" in x[0])
    return {x["key"]: x for x in breakdown}


def test_photo_case_61_days_mid_season_is_not_complete_and_says_why():
    room: dict = {}
    _learn(room, date(2026, 9, 16), 61)                              # 16.09.–15.11.2026, one observation per day
    autumn = _seasons(room)["autumn"]
    assert autumn["observed_days"] == 61 and autumn["optimized"] is False
    assert autumn["covers_start"] is False and autumn["covers_end"] is False and autumn["min_days"] == 60
    assert _seasons(room)["winter"]["observed_days"] == 0             # 60 days never switch to winter


def test_learning_goes_on_after_60_days_and_a_full_season_completes():
    room: dict = {}
    _learn(room, date(2026, 9, 1), 91)                               # 01.09.–30.11.: start and end covered
    autumn = _seasons(room)["autumn"]
    assert autumn["observed_days"] == 91 and autumn["optimized"] is True
    assert autumn["covers_start"] and autumn["covers_end"]
    ctx = seasonal_context(room, datetime(2026, 11, 30, 12, tzinfo=BERLIN))
    assert ctx and ctx.get("season") == "autumn"


def test_coefficients_are_used_before_the_badge_and_keep_learning():
    room: dict = {}
    _learn(room, date(2026, 9, 16), 61)
    before = room["seasonal_source_profiles"]["autumn"]["samples"]
    _learn(room, date(2026, 11, 16), 1)
    assert room["seasonal_source_profiles"]["autumn"]["samples"] == before + 1
    assert len(room["seasonal_observation_days"]["2026:autumn"]) == 62
