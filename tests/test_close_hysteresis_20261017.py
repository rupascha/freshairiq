"""Node-RED feedback (2026-10-17): the raw room action toggled between
"Continue ventilating" and "Close" every minute while the expected return of
the next five minutes hovered around the close threshold.

Once a close was recommended in a running session it is kept until the next
five minutes would beat the threshold by 25 % (``CLOSE_RELEASE_FACTOR``).
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import CLOSE_RELEASE_FACTOR, RoomInput, evaluate_room, scaled_min_return

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 3, "max_duration_min": 30}


def _room(reference_humidity: float, **overrides) -> RoomInput:
    values = dict(
        key="schlaf", name="Schlafzimmer", temperature=20, humidity=62,
        reference_temperature=12, reference_humidity=reference_humidity, volume_m3=40,
        contact_open=True, contact_open_seconds=600, session_active=True, session_elapsed_min=10,
        session_start_temp=20.5, learning_rate=0.03, session_fresh_measurements=3,
    )
    values.update(overrides)
    return RoomInput(**values)


def test_release_factor_and_threshold() -> None:
    assert CLOSE_RELEASE_FACTOR == 1.25
    assert scaled_min_return(OPTIONS["min_return_next_5_min_ml"], 40) == 25.0


def test_jitter_around_the_threshold_no_longer_toggles() -> None:
    # 25 ml is the close threshold; the expected return jitters between 22 and 27 ml
    published = []
    close_notified = False
    for reference_humidity in (60, 64, 58, 66, 60, 62, 58, 64, 60):
        result = evaluate_room(_room(reference_humidity, close_notified=close_notified), OPTIONS, False)
        close_notified = result.close_recommended  # what the coordinator remembers
        published.append(result.action)
    first_close = published.index("Close")
    assert published[:first_close] == ["Continue ventilating"] * first_close
    assert set(published[first_close:]) == {"Close"}
    changes = sum(1 for a, b in zip(published, published[1:]) if a != b)
    assert changes == 1


def test_without_the_latch_the_same_jitter_toggles() -> None:
    # documents the previous behaviour: every cycle decides from scratch
    actions = [evaluate_room(_room(rh), OPTIONS, False).action for rh in (60, 64, 58, 66)]
    assert actions == ["Continue ventilating", "Close", "Continue ventilating", "Close"]


def test_clearly_better_return_releases_the_close() -> None:
    held = evaluate_room(_room(58, close_notified=True), OPTIONS, False)  # ~27 ml < 31.25 ml
    assert held.action == "Close" and held.close_recommended
    released = evaluate_room(_room(45, close_notified=True), OPTIONS, False)
    assert released.next_5_min_ml >= 25.0 * CLOSE_RELEASE_FACTOR
    assert released.action == "Continue ventilating" and not released.close_recommended


def test_maximum_duration_and_thermal_loss_keep_the_close() -> None:
    long_open = evaluate_room(_room(45, close_notified=True, session_elapsed_min=31), OPTIONS, False)
    assert long_open.action == "Close"
    # the room cooled 2 °C in 10 min: a clearly better return does not release the close
    assert evaluate_room(_room(45, close_notified=True, session_start_temp=22), OPTIONS, False).action == "Close"


def test_latch_needs_a_running_session() -> None:
    closed = evaluate_room(_room(60, close_notified=True, contact_open=False, session_active=False), OPTIONS, False)
    assert not closed.close_recommended
