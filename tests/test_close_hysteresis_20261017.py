"""Node-RED feedback (2026-10-17): the raw room action toggled between
"Continue ventilating" and "Close" every minute while the expected return of
the next five minutes hovered around the close threshold.

Once a close was recommended in a running session it is kept until the next
five minutes would beat the threshold by 25 % (``CLOSE_RELEASE_FACTOR``).
"""
from __future__ import annotations

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import (
    CLOSE_RELEASE_DELTA_G_M3, CLOSE_RELEASE_FACTOR, RoomInput, absolute_humidity, evaluate_room, scaled_min_return,
)

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


# Testvermerk 0.26.7.0 (F11, owner decision): a running airing closes only once the reference air no longer dries the
# room (difference ≤ close_delta = 0.4 g/m³), no longer at the 5-minute return threshold. The latch and its release
# hysteresis now sit on that physical limit (release from close_delta + CLOSE_RELEASE_DELTA_G_M3). The scenarios below
# jitter the reference air around the new limit instead of around 25 ml – the same checks as before.
def _ref_rh(delta: float, room_temp: float = 20.0, room_rh: float = 62.0, ref_temp: float = 19.5) -> float:
    """Reference RH at ``ref_temp`` that is ``delta`` g/m³ drier than the room (bisection on the model's own formula)."""
    target = absolute_humidity(room_temp, room_rh) - delta
    low, high = 0.0, 100.0
    for _ in range(60):
        mid = (low + high) / 2.0
        low, high = (mid, high) if absolute_humidity(ref_temp, mid) < target else (low, mid)
    return round((low + high) / 2.0, 4)


def _near(delta: float, **overrides) -> RoomInput:
    return _room(_ref_rh(delta), reference_temperature=19.5, session_start_temp=20.0, **overrides)


def test_jitter_around_the_threshold_no_longer_toggles() -> None:
    # 0.4 g/m³ is the close limit; the measured difference jitters between 0.30 and 0.60 g/m³
    published = []
    close_notified = False
    for delta in (0.60, 0.30, 0.55, 0.35, 0.60, 0.45, 0.30, 0.55, 0.60):
        result = evaluate_room(_near(delta, close_notified=close_notified), OPTIONS, False)
        close_notified = result.close_recommended  # what the coordinator remembers
        published.append(result.action)
    first_close = published.index("Close")
    assert published[:first_close] == ["Continue ventilating"] * first_close
    assert set(published[first_close:]) == {"Close"}
    changes = sum(1 for a, b in zip(published, published[1:]) if a != b)
    assert changes == 1


def test_without_the_latch_the_same_jitter_toggles() -> None:
    # documents the previous behaviour: every cycle decides from scratch
    actions = [evaluate_room(_near(delta), OPTIONS, False).action for delta in (0.60, 0.30, 0.55, 0.35)]
    assert actions == ["Continue ventilating", "Close", "Continue ventilating", "Close"]


def test_clearly_better_return_releases_the_close() -> None:
    assert CLOSE_RELEASE_DELTA_G_M3 == 0.3
    held = evaluate_room(_near(0.6, close_notified=True), OPTIONS, False)  # 0.6 < 0.4 + 0.3
    assert held.action == "Close" and held.close_recommended
    released = evaluate_room(_near(0.9, close_notified=True), OPTIONS, False)
    assert released.action == "Continue ventilating" and not released.close_recommended


def test_maximum_duration_and_thermal_loss_keep_the_close() -> None:
    # Testvermerk 0.26.7.0 (F11): neither a long airing nor a cooling room keeps a close while confirmed readings prove
    # drying again; the close stays while the air does not dry, and the user's temperature limit closes on its own
    assert evaluate_room(_near(0.9, close_notified=True, session_elapsed_min=120), OPTIONS, False).action == "Continue ventilating"
    assert evaluate_room(_near(0.5, close_notified=True, session_elapsed_min=120), OPTIONS, False).action == "Close"
    cold = {**OPTIONS, "airing_min_room_temp_c": 20.0}
    assert evaluate_room(_room(45, close_notified=False, session_elapsed_min=12), cold, False).action == "Close"


def test_latch_needs_a_running_session() -> None:
    closed = evaluate_room(_room(60, close_notified=True, contact_open=False, session_active=False), OPTIONS, False)
    assert not closed.close_recommended
