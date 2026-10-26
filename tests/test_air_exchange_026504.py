"""0.26.5.4 (community, HarryP): how much of the room air an airing has exchanged.

Display only: share already exchanged and minutes until 95 % under the current
conditions (learned rate × airflow × cross ventilation). No goal, no priority,
no influence on any recommendation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from custom_components.freshairiq.air_exchange import DISPLAY_TARGET, advance_air_exchange

T0 = datetime(2026, 10, 25, 7, 0, tzinfo=timezone.utc)


def _step(mem, minutes, *, rate=0.03, factor=1.0, elapsed=0.0, active=True, learned=True):
    return advance_air_exchange(mem, active=active, elapsed_min=elapsed, now=T0 + timedelta(minutes=minutes),
                                rate_per_min=rate, factor=factor, learned=learned)


def test_share_and_time_to_95_percent_follow_the_learned_rate() -> None:
    mem = {"session_started": "s1"}
    first = _step(mem, 0)
    assert first["exchanged_percent"] == 0
    assert first["minutes_to_95"] == round(math.log(1 - DISPLAY_TARGET) / math.log(0.97), 1) == 98.4
    after = _step(mem, 10)
    assert after["exchanged_percent"] == 26 and after["minutes_to_95"] == 88.4
    assert after["rate_per_min"] == 0.03 and after["estimate"] is False


def test_better_conditions_shorten_the_remaining_time_at_once() -> None:
    mem = {"session_started": "s1"}
    _step(mem, 0)
    tilted = _step(mem, 10)
    cross = _step(mem, 10, factor=1.25 * 1.5)  # second window opened, good wind
    assert cross["exchanged_percent"] == tilted["exchanged_percent"]  # what is exchanged stays exchanged
    assert cross["minutes_to_95"] < tilted["minutes_to_95"] / 1.8


def test_practically_complete_and_no_rate() -> None:
    mem = {"session_started": "s1"}
    _step(mem, 0, rate=0.2)
    done = _step(mem, 30, rate=0.2)
    assert done["exchanged_percent"] >= 95 and done["minutes_to_95"] == 0.0
    still = _step({"session_started": "s2"}, 0, rate=0.0)
    assert still == {"exchanged_percent": 0, "minutes_to_95": None, "rate_per_min": 0.0, "estimate": False}
    assert _step({}, 0, rate="x")["minutes_to_95"] is None
    assert _step({}, 0, rate=float("nan"))["rate_per_min"] == 0.0
    assert _step({}, 0, rate=5.0)["rate_per_min"] == 0.95  # bounded like the model


def test_new_airing_restart_and_damaged_memory_start_from_the_elapsed_time() -> None:
    mem = {"session_started": "s1"}
    _step(mem, 0)
    mem["session_started"] = "s2"  # a new airing
    assert _step(mem, 5, elapsed=0)["exchanged_percent"] == 0
    restarted = {"session_started": "s3"}  # nothing remembered after a restart
    assert _step(restarted, 0, elapsed=10)["exchanged_percent"] == 26
    damaged = {"session_started": "s1", "air_exchange": {"session": "s1", "share": "x", "at": "never"}}
    assert _step(damaged, 0, elapsed="x")["exchanged_percent"] == 0
    assert _step({}, 0, elapsed=None, learned=False)["estimate"] is True


def test_no_airing_no_display() -> None:
    mem = {"session_started": "s1"}
    _step(mem, 0)
    assert _step(mem, 5, active=False) is None and "air_exchange" not in mem
