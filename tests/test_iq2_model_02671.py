"""IQ2 (0.26.7.1): consistent physics, hierarchical learning, forecast quality – the pure model (``iq2`` / ``iq2_runtime``).

All houses and airings here are synthetic. They prove consistency, bounds and learning behaviour of the model – not
its accuracy in real homes (that needs field data, see docs/IQ2.md).
"""
from __future__ import annotations

import math
import random

import pytest

from custom_components.freshairiq import iq2
from custom_components.freshairiq import iq2_runtime as rt
from custom_components.freshairiq.energy import exchanged_air_fraction
from custom_components.freshairiq.model import update_learning
from custom_components.freshairiq.start_model import observed_exchange_rate


# ------------------------------------------------------------------------------------------------ physics

@pytest.mark.parametrize("rate", [0.0, 0.002, 0.016, 0.03, 0.04, 0.25])
def test_rate_conversions_are_exact_inverses(rate):
    assert iq2.k_to_fraction(iq2.fraction_to_k(rate)) == pytest.approx(rate, abs=1e-12)


@pytest.mark.parametrize("bad", [float("nan"), -0.1, 1.0, 2.0])
def test_invalid_rates_raise_instead_of_being_clamped(bad):
    with pytest.raises(ValueError):
        iq2.fraction_to_k(bad)
    with pytest.raises(ValueError):
        iq2.k_to_fraction(float("nan") if bad != -0.1 else -0.1)


@pytest.mark.parametrize("minutes", [5, 10, 15, 20, 30, 60])
def test_forward_and_inverse_are_exact_for_every_duration(minutes):
    """Chapter 4.1 of the order: the same real exchange rate must come back for 5 … 60 minutes."""
    k = 0.03
    rate = iq2.k_to_fraction(k)
    end = 5.0 + (12.0 - 5.0) * math.exp(-k * minutes)
    assert iq2.relax(12.0, 5.0, None, rate, minutes) == pytest.approx(end, abs=1e-9)
    assert iq2.net_fraction(rate, minutes) == pytest.approx(exchanged_air_fraction(rate, minutes), abs=1e-12)
    assert iq2.infer_rate(start=12.0, end=end, source=5.0, minutes=minutes) == pytest.approx(rate, abs=1e-9)
    # the two earlier inversions (learning and start model) are the same exact inverse now
    assert observed_exchange_rate(start_ah=12.0, end_ah=end, source_ah=5.0, elapsed_min=minutes) == pytest.approx(rate, abs=1e-5)
    learned, _n, text, valid = update_learning(old_rate=0.03, old_samples=30, elapsed_min=minutes, start_ah=12.0, end_ah=end,
                                               source_ah=5.0, learning_enabled=True)
    assert valid and "Learned" in text and learned == pytest.approx(0.03, abs=0.001)   # no shrinking with the duration


def test_learning_rejects_what_an_end_point_cannot_identify():
    """A plateau says nothing about the speed; an implausibly fast airing is rejected with its own reason."""
    kw = dict(old_rate=0.03, old_samples=10, source_ah=5.0, learning_enabled=True)
    rate, samples, text, valid = update_learning(elapsed_min=30.0, start_ah=12.0, end_ah=5.3, **kw)   # 96 % of the difference
    assert (rate, samples, valid) == (0.03, 10, False) and "not identifiable" in text
    rate, samples, text, valid = update_learning(elapsed_min=2.0, start_ah=12.0, end_ah=8.5, **kw)    # half of it in 2 minutes
    assert (rate, samples, valid) == (0.03, 10, False) and text == "Rejected: learning rate 0.293/min > 0.25"
    assert update_learning(elapsed_min=10.0, start_ah=5.0, end_ah=4.9, source_ah=5.0, old_rate=0.03, old_samples=10,
                           learning_enabled=True)[3] is False                            # no difference: nothing divides by zero


@pytest.mark.parametrize("rate", [0.0, 0.004, 0.03, 0.12, 0.6, 1.4, -0.2])
@pytest.mark.parametrize("airflow,cross", [(1.0, False), (0.3, False), (1.5, True), (2.4, True)])
@pytest.mark.parametrize("share", [1.0, 0.15, 0.02, 0.0005, 3.0])
def test_room_model_five_minute_values_are_the_iq2_physics(rate, airflow, cross, share):
    """The room model writes the 5-minute physics out (it runs for every room in every cycle); it must stay the same
    physics as ``iq2.net_fraction`` / ``iq2.relax``."""
    from custom_components.freshairiq.const import DEFAULT_OPTIONS
    from custom_components.freshairiq.model import RoomInput, evaluate_room

    room = RoomInput(key="r", name="R", temperature=21.0, humidity=64.0, reference_temperature=4.0, reference_humidity=80.0,
                     volume_m3=40.0, contact_open=False, contact_open_seconds=0.0, learning_rate=rate, airflow_factor=airflow,
                     thermal_air_share=share)
    result = evaluate_room(room, DEFAULT_OPTIONS, cross)
    bonus = (1.25 if cross else 1.0) * min(max(airflow, 0.5), 1.5)
    fraction = min(iq2.net_fraction(float(rate), 5.0, bonus), 0.85)
    assert result.moisture_effect_next_5_min_ml == pytest.approx(result.delta_g_m3 * 40.0 * fraction, abs=0.6)
    expected_dt = iq2.relax(21.0, 4.0, None, float(rate), 5.0, bonus, float(share)) - 21.0
    assert result.temp_next_5_min_c == pytest.approx(expected_dt, abs=0.0501)   # the room model publishes one decimal


def test_the_earlier_linear_inversion_shrank_with_the_duration():
    k = 0.03
    linear = [(12.0 - (5.0 + 7.0 * math.exp(-k * t))) / 7.0 / t for t in (5, 20, 60)]
    assert linear[0] > linear[1] > linear[2] and linear[2] < 0.015                     # 0.0279, 0.0226, 0.0139


@pytest.mark.parametrize("share", [1.0, 0.6, 0.35])
@pytest.mark.parametrize("minutes", [5, 20, 60])
def test_buffered_forward_and_inverse_are_consistent(share, minutes):
    end = iq2.relax(11.0, 5.0, 11.0, 0.03, minutes, 1.0, share)
    removed = (11.0 - end) / 6.0
    assert removed == pytest.approx(iq2.net_fraction(0.03, minutes, 1.0, share), abs=1e-9)
    inferred = iq2.infer_rate(start=11.0, end=end, source=5.0, minutes=minutes, share=share)
    if removed < iq2.SATURATION_LIMIT * share:
        assert inferred == pytest.approx(0.03, abs=1e-9)
    else:
        assert inferred is None                                                        # plateau: rate not identifiable
    assert iq2.infer_share(removed_fraction=removed, rate=0.03, minutes=minutes, minimum=0.1) == pytest.approx(share, abs=1e-4)


def test_net_removal_is_bounded_by_the_share_and_monotone_at_steady_conditions():
    for share in (1.0, 0.5, 0.2):
        previous = 0.0
        for minutes in range(1, 181):
            value = iq2.net_fraction(0.05, minutes, 1.0, share)
            assert previous - 1e-12 <= value <= min(share, 0.95) + 1e-12
            previous = value


def test_relax_edge_cases_zero_exchange_zero_difference_and_reversal():
    assert iq2.relax(9.0, 5.0, None, 0.0, 30.0) == 9.0                                  # no exchange: nothing changes
    assert iq2.relax(9.0, 9.0, None, 0.03, 30.0) == pytest.approx(9.0)                  # no difference
    assert iq2.relax(6.0, 9.0, None, 0.03, 10.0) > 6.0                                  # wetter reference adds moisture
    assert iq2.relax(9.0, 5.0, 10.0, 0.03, 0.0, 1.0, 0.5) == 9.0                        # no time
    assert iq2.relax(9.0, 5.0, None, 0.03, 600.0) == pytest.approx(5.0 + 4.0 * 0.05)    # bounded like the earlier model
    assert iq2.effective_rate("x", None) == 0.0 and iq2.effective_rate(0.5, 3.0) == 0.95


@pytest.mark.parametrize("kw", [
    dict(start=None, end=9.0, source=5.0, minutes=10), dict(start=10.0, end=9.0, source=5.0, minutes=1.0),
    dict(start=10.0, end=9.0, source=5.0, minutes=200.0), dict(start=10.0, end=9.0, source=9.8, minutes=10),
    dict(start=10.0, end=9.99, source=5.0, minutes=10), dict(start=10.0, end=11.0, source=5.0, minutes=10),
    dict(start=10.0, end=5.2, source=5.0, minutes=10), dict(start=10.0, end=4.0, source=5.0, minutes=10),
    dict(start=10.0, end=9.9, source=5.0, minutes=100), dict(start=10.0, end=6.0, source=5.0, minutes=2.0),
    dict(start=float("nan"), end=9.0, source=5.0, minutes=10),
])
def test_unusable_airings_teach_nothing(kw):
    assert iq2.infer_rate(**kw) is None


def test_infer_share_limits():
    assert iq2.infer_share(removed_fraction=None, rate=0.03, minutes=10, minimum=0.1) is None
    assert iq2.infer_share(removed_fraction=0.2, rate=0.03, minutes=1, minimum=0.1) is None
    assert iq2.infer_share(removed_fraction=-0.1, rate=0.03, minutes=10, minimum=0.1) is None
    assert iq2.infer_share(removed_fraction=0.9, rate=0.03, minutes=10, minimum=0.1) == 1.0     # more than plain mixing
    assert iq2.infer_share(removed_fraction=0.01, rate=0.03, minutes=60, minimum=0.1) == 0.1    # below the minimum share


def test_one_end_point_is_shared_between_rate_and_air_share_by_what_it_can_tell():
    exact = iq2.joint_targets(removed_fraction=iq2.net_fraction(0.03, 20, 1.0, 0.5), rate=0.03, minutes=20, share=0.5)
    assert exact == (pytest.approx(0.03, abs=1e-9), pytest.approx(0.5, abs=1e-9))       # forecast was right: nothing moves
    short_rate, short_share = iq2.joint_targets(removed_fraction=0.14, rate=0.03, minutes=4, share=0.5)
    assert math.log(short_rate / 0.03) > 4 * math.log(short_share / 0.5) > 0             # a short airing teaches the rate
    long_rate, long_share = iq2.joint_targets(removed_fraction=0.80, rate=0.03, minutes=90, share=0.5)
    assert math.log(long_share / 0.5) > 4 * math.log(long_rate / 0.03) > 0               # a plateau teaches the air share
    slow_rate, slow_share = iq2.joint_targets(removed_fraction=0.05, rate=0.03, minutes=20, share=0.5)
    assert slow_rate < 0.03 and slow_share < 0.5 and slow_rate >= 0.015                 # bounded: at most a factor of two
    assert iq2.joint_targets(removed_fraction=0.99, rate=0.01, minutes=120, share=0.8)[1] == 1.0  # the share never exceeds 1
    for bad in (dict(removed_fraction=None, rate=0.03, minutes=10, share=0.5), dict(removed_fraction=0.2, rate=0.03, minutes=0, share=0.5),
                dict(removed_fraction=0.2, rate=0.0, minutes=10, share=0.5), dict(removed_fraction=0.2, rate=0.03, minutes=None, share=0.5),
                dict(removed_fraction=0.2, rate=1e-9, minutes=1e-9, share=1.0)):
        assert iq2.joint_targets(**bad) is None


# ------------------------------------------------------------------------------------------------ posteriors and state

def test_posterior_votes_are_bounded_and_invalid_votes_change_nothing():
    post = iq2.new_posterior()
    assert iq2.offset(post, 8.0) == 0.0 and iq2.offset(post, 8.0, 0.3) == pytest.approx(0.3)
    assert iq2.vote(post, None, 1.0, 1.0) == post and iq2.vote(post, 2.0, 1.0, 0.0) == post
    assert iq2.vote(post, float("inf"), 1.0, 1.0) == post and iq2.vote(post, -1.0, 1.0, 1.0) == post
    assert iq2.vote(post, 2.0, 0.0, 1.0) == post and iq2.vote(post, 2.0, 1.0, "x") == post
    extreme = iq2.vote(post, 100.0, 1.0, 5.0)                                           # one airing: at most factor two
    assert extreme == {"sum": round(math.log(2.0), 6), "weight": 1.0, "n": 1}
    moved = iq2.vote(post, 100.0, 1.0, 1.0, 1.0)                                        # bound follows the current estimate
    assert moved["sum"] == pytest.approx(1.0 + math.log(2.0), abs=1e-6)
    full = iq2.vote({"sum": 4.0, "weight": iq2.EVIDENCE_MEMORY, "n": 90}, 1.0, 1.0, 1.0)
    memory = iq2.EVIDENCE_MEMORY                                                         # older votes fade, the counter goes on
    assert full["weight"] == memory and full["sum"] == pytest.approx(4.0 * memory / (memory + 1), abs=1e-5) and full["n"] == 91
    # the prior fades as the room's own evidence fills the memory
    assert iq2.offset(iq2.new_posterior(), 8.0, 0.3) == pytest.approx(0.3)
    half = {"sum": 0.5 * memory / 2, "weight": memory / 2, "n": 9}
    assert 0.3 < iq2.offset(half, 8.0, 0.3) < 0.5
    assert iq2.offset({"sum": 0.5 * memory, "weight": memory, "n": 30}, 8.0, 0.3) == pytest.approx(0.5)
    assert iq2.offset({"sum": 0.0, "weight": 0.0, "n": 0}, 0.0, 0.2) == 0.2                # no prior, no evidence: the prior mean
    assert iq2.vote("broken", 1.5, 1.0, 0.5)["n"] == 1
    assert iq2.vote({"sum": "x", "weight": 1}, 1.5, 1.0, 0.5)["weight"] == 0.5          # malformed posterior starts fresh
    assert iq2.vote({"sum": 0.1, "weight": -1}, 1.5, 1.0, 0.5)["weight"] == 0.5


def test_states_are_sanitised_and_other_schemas_start_empty():
    assert iq2.house_state(None) == iq2.new_house_state() and iq2.house_state({"schema": 99}) == iq2.new_house_state()
    dirty = {"schema": iq2.SCHEMA, "rate": {"open": {"sum": 0.2, "weight": 1.0, "n": 1}, "nonsense": {}}, "moisture_share": "x",
             "thermal_share": {"sum": 0.1, "weight": 2.0, "n": 2}, "score": {"n": 3, "evil": 1}, "seeded_from_legacy": 1}
    room = iq2.room_state(dirty)
    assert set(room["rate"]) == {"open"} and room["moisture_share"] == iq2.new_posterior()
    assert room["score"]["n"] == 3 and "evil" not in room["score"] and room["seeded_from_legacy"] is True
    assert iq2.room_state({"schema": iq2.SCHEMA, "rate": [], "score": []})["score"] == iq2.new_score()
    assert "score" not in iq2.house_state(dirty)


def test_cold_start_new_room_in_a_learned_house_and_room_evidence():
    assert iq2.parameters(None, None, "open", 0.03) == {
        "rate": 0.03, "moisture_share": 0.5, "thermal_share": 0.15, "mode": "open", "base_rate": 0.03,
        "room_weight": 0.0, "room_airings": 0, "house_weight": 0.0, "level": "global"}
    assert iq2.parameters(None, None, "nonsense", None)["mode"] == iq2.GENERAL
    house = iq2.new_house_state()
    for _ in range(12):                                                                 # the house airs twice as fast
        house["rate"]["open"] = iq2.vote(house["rate"].get("open"), iq2.fraction_to_k(0.06), iq2.fraction_to_k(0.03), 1.0)
    new_room = iq2.parameters(None, house, "open", 0.03)
    assert new_room["level"] == "house" and 0.03 < new_room["rate"] < 0.06              # profits, but shrunk
    assert iq2.parameters(None, house, "tilted", 0.015)["rate"] == 0.015                # other ways of airing: untouched
    room = iq2.new_room_state()
    for _ in range(30):
        room["rate"]["open"] = iq2.vote(room["rate"].get("open"), iq2.fraction_to_k(0.02), iq2.fraction_to_k(0.03), 1.0)
        if _ == 3:                                                                      # four airings: between house and room
            assert 0.02 < iq2.parameters(room, house, "open", 0.03)["rate"] < new_room["rate"]
    own = iq2.parameters(room, house, "open", 0.03)
    assert own["level"] == "room" and own["rate"] == pytest.approx(0.02, rel=0.01)      # a full memory: its own evidence


def test_earlier_learning_seeds_a_room_as_weak_discounted_evidence():
    legacy = {iq2.GENERAL: (0.02, 40, 0.03), "tilted": (0.01, 1, 0.015), "open": (0.03, 0, 0.03), "bogus": (0.02, 5, 0.03),
              "cross": ("x", 5, 0.04), "mechanical_exhaust": (0.9, 5, 0.02)}
    state = iq2.room_state(None, legacy=legacy)
    assert state["seeded_from_legacy"] is True and set(state["rate"]) == {iq2.GENERAL, "tilted"}
    assert state["rate"][iq2.GENERAL]["weight"] == iq2.LEGACY_SEED_MAX_WEIGHT and state["rate"]["tilted"]["weight"] == 0.5
    seeded = iq2.parameters(state, None, iq2.GENERAL, 0.03)["rate"]
    assert 0.02 < seeded < 0.03                                                         # towards the earlier rate, not equal to it
    assert iq2.room_state(None)["seeded_from_legacy"] is False
    assert iq2.room_state(state) == state                                               # seeding happens once


def test_running_airing_never_claims_less_than_already_removed():
    assert iq2.session_share(0.5, start=10.0, now=8.0, source=5.0) == 0.5               # 40 % removed < share
    assert iq2.session_share(0.5, start=10.0, now=6.5, source=5.0) == pytest.approx(0.7)
    assert iq2.session_share(0.5, start=10.0, now=4.0, source=5.0) == 1.0
    assert iq2.session_share(0.5, start=None, now=8.0, source=5.0) == 0.5
    assert iq2.session_share(0.5, start=5.1, now=5.0, source=5.0) == 0.5                # no usable difference


# ------------------------------------------------------------------------------------------------ learning

def _truth_airing(rnd, rate, share, *, noise=0.05):
    minutes = rnd.choice([4, 6, 8, 10, 15, 20, 30, 45, 60, 90])
    start, source = rnd.uniform(9, 13), rnd.uniform(3, 6)
    return minutes, start, source, iq2.relax(start, source, start, rate, minutes, 1.0, share) + rnd.gauss(0, noise)


@pytest.mark.parametrize("true_rate,true_share", [(0.03, 0.35), (0.06, 0.35), (0.012, 0.6), (0.08, 1.0)])
def test_learning_reduces_the_forecast_error_against_the_start_model(true_rate, true_share):
    rnd = random.Random(7)
    room, house, errors = None, None, []
    for i in range(600):
        minutes, start, source, end = _truth_airing(rnd, true_rate, true_share)
        room, house, report = iq2.learn_airing(room, house, mode="open", base_rate=0.03, start_ah=start, end_ah=end, source_ah=source,
                                               minutes=minutes, volume_m3=30.0, quality_weight=1.0, legacy_rate=0.03)
        errors.append(abs(report["predicted_net_ml"] - report["observed_net_ml"]))
        if i == 149:                                                                    # the claim after 150 airings: the forecast
            assert sum(errors[-15:]) / 15 < 0.6 * sum(errors[:15]) / 15
            score = room["score"]
            assert score["n"] == 150 and score["error_ml"] < 0.5 * score["reference_error_ml"] and score["rollback"] is False
            if true_rate != 0.03:
                assert abs(iq2.parameters(room, house, "open", 0.03)["rate"] - true_rate) < 0.75 * abs(0.03 - true_rate)
    # one end point per airing cannot separate rate and air share at once: the share follows more slowly (and may first
    # move the wrong way while the rate is still off) – after a long run both are near the simulated truth
    learned = iq2.parameters(room, house, "open", 0.03)
    assert abs(learned["moisture_share"] - true_share) < abs(iq2.MOISTURE_SHARE_PRIOR - true_share)
    assert learned["rate"] == pytest.approx(true_rate, rel=0.12)


def test_many_consistent_airings_may_leave_the_factor_two_band_and_old_evidence_fades():
    """A room three times as fast as its start value must be learnable; after years a changed room is still followed."""
    rnd = random.Random(11)
    room = house = None
    for _ in range(300):
        minutes, start, source, end = _truth_airing(rnd, 0.09, 1.0)
        room, house, _ = iq2.learn_airing(room, house, mode="open", base_rate=0.03, start_ah=start, end_ah=end, source_ah=source,
                                          minutes=minutes, volume_m3=30.0, quality_weight=1.0)
    assert iq2.parameters(room, house, "open", 0.03)["rate"] == pytest.approx(0.09, rel=0.1)
    for _ in range(1500):                                                               # long run: storage stays bounded
        minutes, start, source, end = _truth_airing(rnd, 0.02, 1.0)
        room, house, _ = iq2.learn_airing(room, house, mode="open", base_rate=0.03, start_ah=start, end_ah=end, source_ah=source,
                                          minutes=minutes, volume_m3=30.0, quality_weight=1.0)
    assert iq2.parameters(room, house, "open", 0.03)["rate"] == pytest.approx(0.02, rel=0.1)
    for state in (room, house):
        assert state["rate"]["open"]["weight"] <= iq2.EVIDENCE_MEMORY and state["moisture_share"]["weight"] <= iq2.EVIDENCE_MEMORY
    assert room["rate"]["open"]["n"] > 1000 and len(repr(room)) < 1200                   # a counter, never a growing list


def test_one_extreme_airing_does_not_take_over_the_model():
    room, house, report = iq2.learn_airing(None, None, mode="open", base_rate=0.03, start_ah=12.0, end_ah=7.5, source_ah=5.0,
                                           minutes=4.0, volume_m3=30.0, quality_weight=1.0)
    # bound of one vote in a new one-room house: the room's vote (ln 2 against a prior of ≈ 7.3 airings) plus the house
    # prior it leans on, moved by the same airing (ln 2 against ≈ 5.5) → at most a factor of 1.2
    assert report["usable"] and 0.03 < report["rate_after"] <= 0.03 * 1.2


def test_parallel_rooms_share_one_house_vote_and_polling_is_no_evidence():
    kw = dict(mode="open", base_rate=0.03, start_ah=12.0, end_ah=10.5, source_ah=5.0, minutes=8.0, volume_m3=30.0, quality_weight=1.0)
    _room, alone, _ = iq2.learn_airing(None, None, **kw)
    house = None
    for _ in range(10):                                                                 # ten rooms aired together
        _room, house, _ = iq2.learn_airing(None, house, parallel_rooms=10, **kw)
    # one house vote in total; the tiny rest comes from the estimate moving between the ten partial votes
    assert house["rate"]["open"]["weight"] == pytest.approx(alone["rate"]["open"]["weight"], rel=0.02)
    assert house["rate"]["open"]["sum"] == pytest.approx(alone["rate"]["open"]["sum"], rel=0.05)
    assert house["rate"]["open"]["n"] == 10


@pytest.mark.parametrize("kw", [
    dict(quality_weight=0.0), dict(minutes=1.0), dict(minutes=500.0), dict(source_ah=11.8), dict(volume_m3=0.0),
    dict(start_ah=None), dict(end_ah="x"),
])
def test_unusable_airing_changes_nothing(kw):
    base = dict(mode="open", base_rate=0.03, start_ah=12.0, end_ah=10.5, source_ah=5.0, minutes=8.0, volume_m3=30.0, quality_weight=1.0)
    room, house, report = iq2.learn_airing(None, None, **{**base, **kw})
    assert report["usable"] is False and room == iq2.new_room_state() and house == iq2.new_house_state()


def test_a_room_that_got_wetter_is_scored_but_teaches_no_exchange_rate():
    room, house, report = iq2.learn_airing(None, None, mode="open", base_rate=0.03, start_ah=10.0, end_ah=10.4, source_ah=5.0,
                                           minutes=20.0, volume_m3=30.0, quality_weight=1.0)
    assert report["usable"] and "observed_rate" not in report and "observed_moisture_share" not in report
    assert room["rate"] == {} and room["score"]["n"] == 1 and house["rate"] == {}


def test_thermal_share_is_learned_from_the_temperature_and_never_from_short_or_flat_airings():
    kw = dict(mode="open", base_rate=0.03, start_ah=12.0, end_ah=10.0, source_ah=5.0, minutes=30.0, volume_m3=30.0, quality_weight=1.0)
    room, _h, report = iq2.learn_airing(None, None, start_temp=20.0, end_temp=19.0, source_temp=2.0, **kw)
    assert report["observed_thermal_share"] == pytest.approx(1.0 / 18.0, abs=0.01)
    assert iq2.parameters(room, None, "open", 0.03)["thermal_share"] < iq2.THERMAL_SHARE_PRIOR
    _r, _h, warm = iq2.learn_airing(None, None, start_temp=20.0, end_temp=20.5, source_temp=2.0, **kw)   # heating / sun
    assert warm["observed_thermal_share"] == iq2.THERMAL_SHARE_MIN
    for extra in (dict(start_temp=20.0, end_temp=19.0, source_temp=18.5), dict(start_temp=20.0, end_temp=19.0, source_temp=2.0, minutes=6.0),
                  dict(start_temp=None, end_temp=19.0, source_temp=2.0)):
        assert "observed_thermal_share" not in iq2.learn_airing(None, None, **{**kw, **extra})[2]


# ------------------------------------------------------------------------------------------------ forecast quality

def test_interval_is_published_only_after_calibration_and_tracks_the_coverage_target():
    rnd = random.Random(3)
    state = iq2.new_room_state()
    assert iq2.forecast_quality(state, 50.0) == {
        "model": "iq2", "scored_airings": 0, "state": "collecting", "coverage_target_percent": 80, "interval_ml": None,
        "observed_coverage_percent": None, "mean_error_ml": None, "rollback": False}
    covered = 0
    for i in range(400):
        predicted = rnd.uniform(40, 120)
        observed = predicted * (1.0 + rnd.gauss(0, 0.3))
        quality = iq2.forecast_quality(state, predicted)
        if i >= 100 and quality["interval_ml"] is not None:
            covered += quality["interval_ml"][0] <= observed <= quality["interval_ml"][1]
        state["score"] = iq2.update_score(state["score"], predicted, observed, None)
    assert 0.70 <= covered / 300 <= 0.90                                                # long-run coverage near 80 %
    final = iq2.forecast_quality(state, 100.0)
    assert final["state"] == "calibrated" and final["interval_ml"][0] < 100 < final["interval_ml"][1]
    assert iq2.forecast_quality(state, None)["interval_ml"] is None
    assert iq2.forecast_quality(state, 2.0)["interval_ml"][1] - 2.0 >= 0.05 * iq2.SCORE_FLOOR_ML    # floor for tiny forecasts


def test_rollback_guard_needs_evidence_and_recovers():
    score = None
    for _ in range(iq2.ROLLBACK_MIN_SCORED - 1):
        score = iq2.update_score(score, 100.0, 20.0, 25.0)                              # ours far off, reference close
    assert score["rollback"] is False                                                   # not on a handful of airings
    score = iq2.update_score(score, 100.0, 20.0, 25.0)
    assert score["rollback"] is True
    for _ in range(30):
        score = iq2.update_score(score, 22.0, 20.0, 60.0)                               # ours good again
    assert score["rollback"] is False
    assert iq2.update_score({"n": "x", "quantile": "y"}, 10.0, 10.0, None)["n"] == 1    # malformed score starts clean


# ------------------------------------------------------------------------------------------------ published fields

def test_room_and_house_fields_keep_the_quantities_apart():
    dynamic = {"net_room_change_ml": 36, "outdoor_transport_ml": 76, "to_target_ml": 0}
    params = dict(iq2.parameters(None, None, "open", 0.03), active=True)
    room = iq2.room_fields(params, None, dynamic)
    assert (room["forecast_net_room_change_ml"], room["forecast_outdoor_transport_ml"], room["forecast_to_target_ml"]) == (36, 76, 0)
    assert room["forecast_interval_ml"] is None and room["forecast_quality"]["state"] == "collecting"
    assert room["iq2"] == {"model": "iq2", "active": True, "level": "global", "mode": "open", "rate_per_min": 0.03,
                           "moisture_air_share": 0.5, "thermal_air_share": 0.15, "room_airings": 0}
    passive = iq2.room_fields({"active": False, "rate": 0.03}, None, None)
    assert passive["forecast_quality"]["state"] == "not_applicable" and passive["forecast_net_room_change_ml"] is None
    assert iq2.room_fields(None, None, None)["iq2"]["active"] is False

    def aired(key, net, interval, target, scored, **extra):
        return {"key": key, "data_quality": "ok", "active": True, "forecast_net_room_change_ml": net, "forecast_outdoor_transport_ml": net * 2,
                "forecast_to_target_ml": target, "forecast_interval_ml": interval, "forecast_quality": {"scored_airings": scored}, **extra}

    empty = iq2.house_fields({"a": {"active": False}, "b": aired("b", 5, None, None, 0, session_finalization_pending=True), "c": "x"})
    assert set(empty.values()) == {None} and set(iq2.house_fields(None).values()) == {None}
    mixed = iq2.house_fields({"a": aired("a", 30, [10, 50], 0, 12), "b": aired("b", 20, None, None, 2)})
    assert mixed == {"forecast_net_room_change_ml": 50, "forecast_outdoor_transport_ml": 100, "forecast_to_target_ml": 0,
                     "forecast_interval_ml": None, "forecast_quality_state": "collecting", "forecast_scored_airings": 2}
    calibrated = iq2.house_fields({"a": aired("a", 30, [10, 50], 0, 12), "b": aired("b", 20, [5, 35], 40, 9)})
    assert calibrated["forecast_interval_ml"] == [15, 85] and calibrated["forecast_quality_state"] == "calibrated"
    assert calibrated["forecast_to_target_ml"] == 40
    assert iq2.house_fields({"a": aired("a", 30, None, None, 0)})["forecast_to_target_ml"] is None


# ------------------------------------------------------------------------------------------------ runtime helpers

def test_runtime_selects_seeds_and_falls_back():
    assert rt.iq2_base_rate({}, iq2.GENERAL) == 0.03 and rt.iq2_base_rate({}, "tilted") == 0.015
    assert rt.iq2_base_rate({"start_model": {"rates": {"open": 0.045}}}, iq2.GENERAL) == 0.045
    assert rt.iq2_base_rate({"start_model": {"rates": {"cross": "x"}}}, "cross") == 0.04
    assert rt.iq2_base_rate({"start_model": "broken"}, "unknown") == 0.03
    passive, seeded = rt.iq2_room_parameters({}, None, mode=None, legacy_rate=0.021, has_contact=False, force_physics=False)
    assert passive["active"] is False and passive["rate"] == 0.021 and passive["moisture_share"] == 1.0 and seeded is False
    # a fan-only airing (window closed) keeps the exhaust model its own sessions learned – no window model, no seeding
    untouched: dict = {"learning_rate": 0.03, "learning_samples": 4}
    fan, seeded = rt.iq2_room_parameters(untouched, None, mode=rt.EXHAUST_MODE, legacy_rate=0.08, has_contact=True, force_physics=False)
    assert (fan["rate"], fan["moisture_share"], fan["thermal_share"], fan["level"], fan["active"]) == (0.08, 1.0, 1.0, "exhaust_model", False)
    assert seeded is False and "iq2" not in untouched and rt.EXHAUST_MODE not in iq2.MODES
    mem = {"learning_rate": 0.02, "learning_samples": 12, "opening_learning": {"tilted": {"rate": 0.01, "samples": 3}, "open": "x"}}
    params, seeded = rt.iq2_room_parameters(mem, None, mode=None, legacy_rate=0.02, has_contact=True, force_physics=False)
    assert seeded is True and mem["iq2"]["seeded_from_legacy"] is True and params["mode"] == iq2.GENERAL and params["active"] is True
    assert 0.02 < params["rate"] < 0.03
    again, seeded = rt.iq2_room_parameters(mem, None, mode="tilted", legacy_rate=0.01, has_contact=True, force_physics=False)
    assert seeded is False and again["mode"] == "tilted" and again["rate"] < 0.015
    forced, _ = rt.iq2_room_parameters(mem, None, mode=None, legacy_rate=0.02, has_contact=True, force_physics=True)
    assert (forced["rate"], forced["moisture_share"], forced["thermal_share"], forced["level"]) == (0.03, 0.5, 0.15, "fallback")
    mem["iq2"]["score"]["rollback"] = True
    back, _ = rt.iq2_room_parameters(mem, None, mode=None, legacy_rate=0.02, has_contact=True, force_physics=False)
    assert (back["rate"], back["moisture_share"], back["level"]) == (0.02, 1.0, "rollback")
    fresh = {"learning_rate": 0.03, "learning_samples": 0}
    assert rt.iq2_room_parameters(fresh, None, mode="open", legacy_rate=0.03, has_contact=True, force_physics=False)[0]["rate"] == 0.03


def test_runtime_forecast_arguments_goal_history_and_interval_physics():
    params = {"moisture_share": 0.5, "thermal_share": 0.15}
    assert rt.iq2_forecast_arguments(params, {}, running=False, current_ah=9.0) == {"moisture_air_share": 0.5, "thermal_air_share": 0.15}
    assert rt.iq2_forecast_arguments(None, {}, running=False, current_ah=9.0) == {"moisture_air_share": 1.0, "thermal_air_share": 1.0}
    mem = {"session_start_ah": 10.0, "session_start_temp": 20.5, "session_start_source_ah": 5.0}
    running = rt.iq2_forecast_arguments(params, mem, running=True, current_ah=6.0)       # 80 % already removed
    assert running == {"moisture_air_share": pytest.approx(0.8), "thermal_air_share": 0.15, "anchor_ah": 10.0, "anchor_temp_c": 20.5}
    assert rt.iq2_forecast_arguments(params, {}, running=True, current_ah=6.0)["anchor_ah"] is None

    class Result:
        goals_reached_now, goals_in_band = True, True

    history: dict = {}
    assert rt.update_goal_history(history, Result) is True and history["session_goals_reached"] is True
    assert rt.update_goal_history(history, Result) is False
    Result.goals_reached_now = False
    assert rt.update_goal_history(history, Result) is False and history["session_goals_reached"] is True   # held in the band
    Result.goals_in_band = False
    assert rt.update_goal_history(history, Result) is True and history["session_goals_reached"] is False   # goal open again

    removed, cooled = rt.iq2_interval_physics(params, mem, prev_ah=8.0, prev_temp=19.0, ref_ah=5.0, ref_t=3.0, rate=0.03, minutes=10.0,
                                              bonus=1.0, volume=30.0)
    plain, plain_cooled = rt.iq2_interval_physics(None, {}, prev_ah=8.0, prev_temp=19.0, ref_ah=5.0, ref_t=3.0, rate=0.03, minutes=10.0,
                                                  bonus=1.0, volume=30.0)
    assert 0 < removed < plain and plain_cooled < cooled < 0                            # buffer and thermal mass damp both
    assert rt.iq2_interval_physics(params, mem, prev_ah=8.0, prev_temp=None, ref_ah=5.0, ref_t=3.0, rate=0.03, minutes=10.0,
                                   bonus=1.0, volume=30.0)[1] is None
