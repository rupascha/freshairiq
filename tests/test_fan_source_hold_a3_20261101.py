"""Investigation A3 (01.11.): moisture-source follow-up of the exhaust fan with a negative moisture balance.

``decide_fan`` in the mode "after a moisture source" keeps the fan running while ``source_hold`` is true
(recovery window after the source, no window open, house-aligned recommendation says to air), and
does not look at ``safety_off`` (moisture coming in) in that mode – documented: the immediate stop on
moisture coming in belongs to the recommendation mode; the maximum runtime always applies.

The synthetic case (5-minute effect −120 ml together with "continue_ventilating") needs a room whose
own decision says "keep airing" while its moisture effect is negative. The real room model does not
produce that combination for a fan-only room after (or during) a moisture source: checked over a
grid of indoor/outdoor climates, airing times, fresh readings and plateau states. No code change –
whether moisture coming in should end a source follow-up is an owner decision.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.model import RoomInput, evaluate_room

OPTIONS = {**DEFAULT_OPTIONS, "min_duration_min": 3}
BASE = RoomInput(key="bad", name="Bad", temperature=24.0, humidity=75.0, reference_temperature=12.0, reference_humidity=80.0,
                 volume_m3=12.0, contact_open=False, contact_open_seconds=0.0, session_active=True, session_elapsed_min=12.0,
                 session_fresh_measurements=4, mechanical_only=True, moisture_source_recovery=True, moisture_source_ended_min=5.0)
KEEP = {"Continue ventilating", "Ventilate", "Ventilate indirectly"}


def test_a3_the_room_model_never_says_keep_airing_with_moisture_coming_in() -> None:
    kept = 0
    for t_in, rh_in, t_ref, rh_ref, elapsed, fresh, plateau, source in itertools.product(
            [18, 24, 27], [45, 65, 85], [5, 18, 28], [40, 80, 95], [1, 12, 30], [0, 4], [False, True], [False, True]):
        room = replace(BASE, temperature=t_in, humidity=rh_in, reference_temperature=t_ref, reference_humidity=rh_ref,
                       session_elapsed_min=elapsed, session_fresh_measurements=fresh, humidity_plateau=plateau,
                       moisture_source_active=source, moisture_source_recovery=not source)
        result = evaluate_room(room, OPTIONS, False)
        if result.action in KEEP:
            kept += 1
            assert result.moisture_effect_next_5_min_ml >= 0, (room, result.action, result.moisture_effect_next_5_min_ml)
    assert kept > 100  # the grid really contains many "keep airing" answers
