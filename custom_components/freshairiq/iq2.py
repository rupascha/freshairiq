"""IQ2: one consistent physical basis for forecasts, learning and decisions (pure logic, 0.26.7.1).

Physical model (one zone, well mixed) – the reduced form of the zone air moisture balance used by building
simulation (EnergyPlus Engineering Reference, "Moisture Predictor-Corrector": scheduled sources + convection to the
zone surfaces + interzone flows + outdoor air; analytical exponential solution):

    dA/dt = k * (A_out - A) + b * (A_surf - A) [+ G / V]

With the surface/buffer state held at its value when the airing started (``anchor``) the room air relaxes towards

    A_eq = share * A_out + (1 - share) * anchor        share = k / (k + b)   (the air share, 0 < share <= 1)

with the rate ``k / share``. ``share == 1`` is the plain exponential replacement model the integration always used for
its forward forecast (``energy.exchanged_air_fraction``) – then forward and inverse are exact inverses of each other
for every duration. A share below 1 states honestly that walls and furniture give moisture (or heat) back while a
window is open: the *net* change of the room air saturates below the full indoor/outdoor difference although air is
still exchanged. The same form is used for the room temperature (thermal mass instead of moisture buffer).

Units and conversions (exactly once, here):
* ``rate`` – discrete exchanged-air fraction per minute ``r`` (the stored, user-visible "learning rate");
* ``k`` – continuous rate per minute, ``k = -ln(1 - r)``, ``r = 1 - exp(-k)``;
* ``share`` – dimensionless air share of the moisture (or heat) the room air exchanges with.

Learning: bounded log-space posteriors (one validated airing = at most one vote, never one vote per sensor poll)
on three levels – shipped global start values → house → room and way of airing – with shrinkage towards the level
above. Nothing here reads Home Assistant, the network or the clock.
"""
from __future__ import annotations

from math import exp, isfinite, log, log1p, expm1
from typing import Any

MODEL = "iq2"
SCHEMA = 1
MIN_RATE, MAX_RATE = 0.002, 0.25
GENERAL = "general"
MODES = (GENERAL, "open", "tilted", "cross")   # window airing; a fan-only airing keeps its own exhaust model
# global start values of the shares (assumptions, not field-calibrated constants; every house learns its own):
# moisture – between plain mixing (1.0) and the strong buffering seen in long airings; temperature – the room air
# reaches only a small part of the outdoor difference because walls and furniture keep it warm
MOISTURE_SHARE_PRIOR, MOISTURE_SHARE_MIN = 0.5, 0.1
THERMAL_SHARE_PRIOR, THERMAL_SHARE_MIN = 0.15, 0.02
RATE_PRIOR_WEIGHT = 8.0     # airings a room needs to outweigh its prior (research prototype value)
HOUSE_PRIOR_WEIGHT = 6.0
SHARE_PRIOR_WEIGHT = 6.0
MAX_LOG_RESIDUAL = log(2.0)  # one airing votes at most a factor of two away from the current estimate (influence cap, no rate clamp)
EVIDENCE_MEMORY = 12.0       # weighted airings a posterior remembers (as the earlier long-run smoothing of 0.08): a room can still change
SATURATION_LIMIT = 0.92      # beyond this the exchange rate is not identifiable from an end point
LEGACY_SEED_WEIGHT_PER_SAMPLE, LEGACY_SEED_MAX_WEIGHT = 0.5, 3.0
INTERVAL_COVERAGE = 0.8      # target long-run coverage of the forecast interval
INTERVAL_MIN_SCORED = 8      # scored airings before an interval is published
SCORE_FLOOR_ML = 20.0
ROLLBACK_MIN_SCORED = 6
ROLLBACK_FACTOR, ROLLBACK_MARGIN_ML, ROLLBACK_RECOVER_FACTOR = 1.25, 5.0, 1.05


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


# ------------------------------------------------------------------------------------------------ physics

def fraction_to_k(rate: float) -> float:
    """Continuous rate per minute of a discrete per-minute exchange fraction."""
    if not isfinite(rate) or not 0.0 <= rate < 1.0:
        raise ValueError("invalid per-minute exchange fraction")
    return -log1p(-rate)


def k_to_fraction(k: float) -> float:
    if not isfinite(k) or k < 0.0:
        raise ValueError("invalid continuous exchange rate")
    return -expm1(-k)


def effective_rate(rate: Any, bonus: Any = 1.0) -> float:
    """Per-minute fraction with the airflow bonus, bounded like ``energy.exchanged_air_fraction``."""
    # called in every room evaluation: plain floats skip the conversion helper (same result)
    r = (rate if type(rate) is float and isfinite(rate) else _num(rate)) or 0.0
    b = (bonus if type(bonus) is float and isfinite(bonus) else _num(bonus)) or 0.0
    r = 0.0 if r < 0.0 else 0.95 if r > 0.95 else r
    e = r * b if b > 0.0 else 0.0
    return e if e < 0.95 else 0.95


def _share_and_minutes(share: Any, minutes: Any) -> tuple[float, float]:
    s = (share if type(share) is float and isfinite(share) else _num(share)) or 1.0
    t = (minutes if type(minutes) is float and isfinite(minutes) else _num(minutes)) or 0.0
    return (1e-3 if s < 1e-3 else 1.0 if s > 1.0 else s), (t if t > 0.0 else 0.0)


def net_fraction(rate: Any, minutes: Any, bonus: Any = 1.0, share: Any = 1.0) -> float:
    """Part of the indoor/outdoor difference the room air has lost after ``minutes`` (0 … share)."""
    s, t = _share_and_minutes(share, minutes)
    lost = s * (1.0 - (1.0 - effective_rate(rate, bonus)) ** (t / s))
    return lost if lost < 0.95 else 0.95


def relax(state: float, source: float, anchor: float | None, rate: Any, minutes: Any, bonus: Any = 1.0, share: Any = 1.0) -> float:
    """Room state (absolute humidity or temperature) after ``minutes`` of airing.

    ``anchor`` is the buffer state (the room state when the airing started); None = the current state.
    """
    s, t = _share_and_minutes(share, minutes)
    equilibrium = s * source + (1.0 - s) * (state if anchor is None else anchor)
    remaining = (1.0 - effective_rate(rate, bonus)) ** (t / s)
    if s >= 1.0 and remaining < 0.05:
        remaining = 0.05
    return equilibrium + (state - equilibrium) * remaining


def infer_rate(*, start: Any, end: Any, source: Any, minutes: Any, share: Any = 1.0, max_minutes: Any = 120.0) -> float | None:
    """Exchange rate of one finished airing – the exact inverse of ``net_fraction`` for the same share.

    Valid only for a well-mixed room without an inner source and with a steady reference. Unusable airings (too
    short/long, no drying difference, no reduction, saturation, implausible rate) return None; nothing is clamped
    into a learnable value.
    """
    a0, a1, src, t = _num(start), _num(end), _num(source), _num(minutes)
    s = _clamp(_num(share) or 1.0, 1e-3, 1.0)
    limit = _num(max_minutes) or 120.0
    if a0 is None or a1 is None or src is None or t is None or t < 2.0 or t > limit:
        return None
    delta, reduction = a0 - src, a0 - a1
    if delta <= 0.5 or reduction <= 0.05:
        return None
    removed = reduction / delta
    if removed >= SATURATION_LIMIT * s:
        return None
    rate = 1.0 - (1.0 - removed / s) ** (s / t)
    return rate if MIN_RATE <= rate <= MAX_RATE else None


def joint_targets(*, removed_fraction: Any, rate: Any, minutes: Any, share: Any) -> tuple[float, float] | None:
    """(rate per minute, air share) that explain one end point with the smallest joint change of both parameters.

    One end point cannot separate "fast exchange" from "large air share". For the removed fraction
    f = s·(1 − e^(−x)), x = k·t/s, the sensitivities are ∂f/∂ln k = s·x·e^(−x) and ∂f/∂ln s = s·(1 − e^(−x) − x·e^(−x)).
    The forecast error is shared between both parameters in proportion to them (normalised least-squares step in log
    space): a short airing moves the rate, an airing near its plateau moves the share. Each change is bounded.
    """
    removed, t, s = _num(removed_fraction), _num(minutes), _clamp(_num(share) or 1.0, 1e-3, 1.0)
    eff = effective_rate(rate)
    if removed is None or t is None or t <= 0.0 or eff <= 0.0:
        return None
    k = fraction_to_k(eff)
    x = k * t / s
    by_rate, by_share = s * x * exp(-x), s * (1.0 - exp(-x) - x * exp(-x))
    total = by_rate * by_rate + by_share * by_share
    if total <= 1e-12:
        return None
    error = removed - s * (1.0 - exp(-x))
    new_k = k * exp(_clamp(error * by_rate / total, -MAX_LOG_RESIDUAL, MAX_LOG_RESIDUAL))
    new_s = s * exp(_clamp(error * by_share / total, -MAX_LOG_RESIDUAL, MAX_LOG_RESIDUAL))
    return _clamp(k_to_fraction(new_k), MIN_RATE, MAX_RATE), min(new_s, 1.0)


def infer_share(*, removed_fraction: Any, rate: Any, minutes: Any, minimum: float) -> float | None:
    """Air share that explains the observed part of the difference (bisection; monotone in the share)."""
    f, t = _num(removed_fraction), _num(minutes)
    if f is None or t is None or t < 2.0 or f <= 0.0:
        return None
    if f >= net_fraction(rate, t, 1.0, 1.0):
        return 1.0
    low, high = minimum, 1.0
    if f <= net_fraction(rate, t, 1.0, low):
        return low
    for _ in range(40):
        mid = (low + high) / 2.0
        if net_fraction(rate, t, 1.0, mid) < f:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


# ------------------------------------------------------------------------------------------------ posteriors

def new_posterior() -> dict[str, Any]:
    return {"sum": 0.0, "weight": 0.0, "n": 0}


def _posterior(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return new_posterior()
    total, weight = _num(value.get("sum")), _num(value.get("weight"))
    if total is None or weight is None or weight < 0.0:
        return new_posterior()
    return {"sum": total, "weight": weight, "n": max(int(_num(value.get("n")) or 0), 0)}


def offset(posterior: Any, prior_weight: float, prior_mean: float = 0.0) -> float:
    """Shrunk log offset: the prior mean while there is no evidence, the evidence mean once the memory is full.

    The prior counts like remembered airings and fades with them: its weight falls linearly to zero while the room's
    own evidence fills the memory, so a room that really differs from its house is not held back for ever.
    """
    p = _posterior(posterior)
    prior = prior_weight * max(1.0 - p["weight"] / EVIDENCE_MEMORY, 0.0)
    total = prior + p["weight"]
    return (prior * prior_mean + p["sum"]) / total if total > 0.0 else prior_mean


def vote(posterior: Any, observed: float | None, base: float, weight: Any, centre: float = 0.0) -> dict[str, Any]:
    """One bounded vote of a validated airing; invalid input leaves the posterior untouched.

    ``centre`` is the log offset in force before the airing: the vote may differ from it by at most a factor of two, so
    a single airing never takes over, while many consistent airings can move a room as far as the measurements say.
    """
    p = _posterior(posterior)
    w = _num(weight)
    if observed is None or not isfinite(observed) or observed <= 0.0 or base <= 0.0 or w is None or w <= 0.0:
        return p
    w = min(w, 1.0)
    residual = _clamp(log(observed / base), centre - MAX_LOG_RESIDUAL, centre + MAX_LOG_RESIDUAL)
    total, evidence = p["sum"] + w * residual, p["weight"] + w
    fade = min(EVIDENCE_MEMORY / evidence, 1.0)
    return {"sum": round(total * fade, 6), "weight": round(evidence * fade, 6), "n": p["n"] + 1}


# ------------------------------------------------------------------------------------------------ state

def new_room_state() -> dict[str, Any]:
    return {"schema": SCHEMA, "rate": {}, "moisture_share": new_posterior(), "thermal_share": new_posterior(),
            "score": new_score(), "seeded_from_legacy": False}


def new_house_state() -> dict[str, Any]:
    return {"schema": SCHEMA, "rate": {}, "moisture_share": new_posterior(), "thermal_share": new_posterior()}


def new_score() -> dict[str, Any]:
    return {"n": 0, "error_ml": None, "reference_error_ml": None, "quantile": 1.0, "covered": 0, "rollback": False}


def _state(value: Any, fresh: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return fresh
    rates = value.get("rate") if isinstance(value.get("rate"), dict) else {}
    out = dict(fresh)
    out["rate"] = {mode: _posterior(rates.get(mode)) for mode in MODES if mode in rates}
    out["moisture_share"], out["thermal_share"] = _posterior(value.get("moisture_share")), _posterior(value.get("thermal_share"))
    if "score" in fresh:
        score = value.get("score") if isinstance(value.get("score"), dict) else {}
        out["score"] = {**new_score(), **{k: score[k] for k in new_score() if k in score}}
        out["seeded_from_legacy"] = bool(value.get("seeded_from_legacy"))
    return out


def house_state(value: Any) -> dict[str, Any]:
    """A clean house state; anything malformed or of another schema starts empty (the rooms keep their own)."""
    return _state(value, new_house_state())


def room_state(value: Any, *, legacy: dict[str, tuple[Any, Any, Any]] | None = None) -> dict[str, Any]:
    """A clean room state. A room that learned before IQ2 is seeded once from its earlier rates.

    ``legacy`` maps a mode to (earlier rate, its samples, the start value of that mode). The earlier rates were
    learned with the linear short-time inversion (too low for long airings), so they enter as weak, discounted
    evidence that new airings outweigh quickly – never as an exact exponential rate.
    """
    if isinstance(value, dict) and value.get("schema") == SCHEMA:
        return _state(value, new_room_state())
    state = new_room_state()
    for mode, (rate, samples, base) in (legacy or {}).items():
        r, n, b = _num(rate), int(_num(samples) or 0), _num(base)
        if mode not in MODES or r is None or b is None or n <= 0 or not MIN_RATE <= r <= MAX_RATE or not MIN_RATE <= b <= MAX_RATE:
            continue
        weight = min(n * LEGACY_SEED_WEIGHT_PER_SAMPLE, LEGACY_SEED_MAX_WEIGHT)
        state["rate"][mode] = vote(new_posterior(), fraction_to_k(r), fraction_to_k(b), 1.0)
        state["rate"][mode].update({"sum": round(state["rate"][mode]["sum"] * weight, 6), "weight": weight, "n": 0})
        state["seeded_from_legacy"] = True
    return state


def parameters(room: Any, house: Any, mode: str, base_rate: Any) -> dict[str, Any]:
    """The rate and shares in force for a room and way of airing (global → house → room shrinkage)."""
    r_state, h_state = _state(room, new_room_state()), house_state(house)
    key = mode if mode in MODES else GENERAL
    base = _clamp(_num(base_rate) or 0.03, MIN_RATE, MAX_RATE)
    house_rate = offset(h_state["rate"].get(key), HOUSE_PRIOR_WEIGHT)
    room_rate = offset(r_state["rate"].get(key), RATE_PRIOR_WEIGHT, house_rate)
    k = _clamp(fraction_to_k(base) * exp(room_rate), fraction_to_k(MIN_RATE), fraction_to_k(MAX_RATE))

    def share(name: str, prior: float, minimum: float) -> float:
        house_offset = offset(h_state[name], HOUSE_PRIOR_WEIGHT)
        return _clamp(prior * exp(offset(r_state[name], SHARE_PRIOR_WEIGHT, house_offset)), minimum, 1.0)

    evidence = _posterior(r_state["rate"].get(key))
    return {
        "rate": round(k_to_fraction(k), 6),
        "moisture_share": round(share("moisture_share", MOISTURE_SHARE_PRIOR, MOISTURE_SHARE_MIN), 4),
        "thermal_share": round(share("thermal_share", THERMAL_SHARE_PRIOR, THERMAL_SHARE_MIN), 4),
        "mode": key, "base_rate": base,
        "room_weight": round(evidence["weight"], 3), "room_airings": evidence["n"],
        "house_weight": round(_posterior(h_state["rate"].get(key))["weight"], 3),
        "level": "room" if evidence["weight"] >= RATE_PRIOR_WEIGHT else "house" if _posterior(h_state["rate"].get(key))["weight"] > 0 else "global",
    }


def session_share(share: float, *, start: Any, now: Any, source: Any) -> float:
    """The share for the running airing: never below the part of the difference the room has already lost."""
    a0, a1, src = _num(start), _num(now), _num(source)
    if a0 is None or a1 is None or src is None or abs(a0 - src) < 0.3:
        return share
    return _clamp(max(share, (a0 - a1) / (a0 - src)), share, 1.0)


# ------------------------------------------------------------------------------------------------ learning

_AT_CALL = object()


def start_model(room: Any, house: Any, mode: Any, base_rate: Any, reference_rate: Any, effective: Any = None) -> dict[str, Any]:
    """The model a start forecast is made with, frozen for its later score.

    ``rate``/``moisture_share`` are the learned parameters, ``effective_*`` and ``level`` what the forecast really used
    (the learned model, the physics fallback or the rollback to the reference model), ``reference_rate`` the reference.
    """
    p = parameters(room, house, mode if mode in MODES else GENERAL, base_rate)
    e = effective if isinstance(effective, dict) else {}
    return {"model": MODEL, "schema": SCHEMA, "mode": p["mode"], "base_rate": p["base_rate"], "rate": p["rate"],
            "moisture_share": p["moisture_share"], "thermal_share": p["thermal_share"], "reference_rate": _num(reference_rate),
            "level": str(e.get("level") or p["level"]), "effective_rate": _num(e.get("rate")) if e else p["rate"],
            "effective_moisture_share": _num(e.get("moisture_share")) if e else p["moisture_share"]}


def _frozen_start(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("model") != MODEL or value.get("schema") != SCHEMA:
        return None
    rate, share = _num(value.get("rate")), _num(value.get("moisture_share"))
    # a start frozen before the effective parameters were kept was made with the learned model
    used_rate = _num(value.get("effective_rate", rate))
    used_share = _num(value.get("effective_moisture_share", share))
    if any(v is None or not 0.0 < v for v in (rate, share, used_rate, used_share)) or not MIN_RATE <= rate <= MAX_RATE \
            or share > 1.0 or used_share > 1.0:
        return None
    return {"rate": rate, "moisture_share": share, "used_rate": used_rate, "used_moisture_share": used_share,
            "level": str(value.get("level") or "learned"), "reference_rate": _num(value.get("reference_rate"))}


def learn_airing(
    room: Any, house: Any, *, mode: str, base_rate: Any, start_ah: Any, end_ah: Any, source_ah: Any, minutes: Any,
    volume_m3: Any, quality_weight: Any, parallel_rooms: int = 1, legacy_rate: Any = None,
    start_temp: Any = None, end_temp: Any = None, source_temp: Any = None, max_minutes: Any = 120.0,
    house_weight: Any = None, start: Any = _AT_CALL,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Score the start forecast of this airing, then learn from it.

    Returns (room state, house state, report). The caller guarantees the data-quality gates (fresh aligned readings,
    no inner source, steady reference, no cover/quarantine); an unusable airing changes nothing.

    ``start`` is the model frozen when the start forecast was made (``start_model``); without it the parameters in
    force at this call are that model (a forecast made right now). ``start=None`` = no valid start forecast: the
    airing still teaches, but nothing is scored. ``house_weight`` replaces ``quality_weight / parallel_rooms`` as the
    house vote of this airing.
    """
    r_state, h_state = _state(room, new_room_state()), house_state(house)
    key = mode if mode in MODES else GENERAL
    before = parameters(r_state, h_state, key, base_rate)
    frozen = ({"rate": before["rate"], "moisture_share": before["moisture_share"], "used_rate": before["rate"],
               "used_moisture_share": before["moisture_share"], "level": before["level"], "reference_rate": _num(legacy_rate)}
              if start is _AT_CALL else _frozen_start(start))
    a0, a1, src, t, volume = _num(start_ah), _num(end_ah), _num(source_ah), _num(minutes), _num(volume_m3)
    weight = _clamp(_num(quality_weight) or 0.0, 0.0, 1.0)
    limit = _num(max_minutes) or 120.0
    report: dict[str, Any] = {"model": MODEL, "mode": key, "usable": False, "rate_before": before["rate"],
                              "moisture_share_before": before["moisture_share"], "thermal_share_before": before["thermal_share"]}
    if a0 is None or a1 is None or src is None or t is None or volume is None or weight <= 0.0 or not 2.0 <= t <= limit or a0 - src <= 0.5 or volume <= 0:
        return r_state, h_state, report
    removed = (a0 - a1) / (a0 - src)
    observed_ml = (a0 - a1) * volume
    report.update({"usable": True, "observed_net_ml": round(observed_ml, 1), "removed_fraction": round(removed, 4), "scored": frozen is not None})
    if frozen is not None:
        # score, interval and rollback all come from the start of this airing, never from parameters learned since:
        # the interval from the forecast really shown (also physics or rollback), the rollback guard from the learned
        # model it would have used, so a room in rollback can recover once its own model is good again
        predicted_ml = (a0 - src) * volume * net_fraction(frozen["used_rate"], t, 1.0, frozen["used_moisture_share"])
        model_ml = (a0 - src) * volume * net_fraction(frozen["rate"], t, 1.0, frozen["moisture_share"])
        reference = frozen["reference_rate"]
        reference_ml = (a0 - src) * volume * net_fraction(reference, t) if reference is not None else None
        r_state["score"] = update_score(r_state["score"], predicted_ml, observed_ml, reference_ml, model_ml=model_ml)
        report.update(predicted_net_ml=round(predicted_ml, 1), model_predicted_net_ml=round(model_ml, 1), start_level=frozen["level"])

    house_weight = _clamp(_num(house_weight), 0.0, 1.0) if _num(house_weight) is not None else weight / max(int(parallel_rooms), 1)
    report["house_weight"] = round(house_weight, 6)
    # a room that got wetter, or an end value at/below the reference air, says nothing about the air exchange
    targets = (joint_targets(removed_fraction=removed, rate=before["rate"], minutes=t, share=before["moisture_share"])
               if a0 - a1 > 0.05 and removed < 1.0 else None)
    if targets is not None:
        seen_rate, seen_share = targets[0], max(targets[1], MOISTURE_SHARE_MIN)
        base_k, seen_k = fraction_to_k(_clamp(_num(base_rate) or 0.03, MIN_RATE, MAX_RATE)), fraction_to_k(seen_rate)
        r_state["rate"][key] = vote(r_state["rate"].get(key), seen_k, base_k, weight, log(fraction_to_k(before["rate"]) / base_k))
        h_state["rate"][key] = vote(h_state["rate"].get(key), seen_k, base_k, house_weight, offset(h_state["rate"].get(key), HOUSE_PRIOR_WEIGHT))
        r_state["moisture_share"] = vote(r_state["moisture_share"], seen_share, MOISTURE_SHARE_PRIOR, weight, log(before["moisture_share"] / MOISTURE_SHARE_PRIOR))
        h_state["moisture_share"] = vote(h_state["moisture_share"], seen_share, MOISTURE_SHARE_PRIOR, house_weight, offset(h_state["moisture_share"], HOUSE_PRIOR_WEIGHT))
        report["observed_rate"], report["observed_moisture_share"] = round(seen_rate, 5), round(seen_share, 4)

    t0, t1, ts = _num(start_temp), _num(end_temp), _num(source_temp)
    if t0 is not None and t1 is not None and ts is not None and abs(ts - t0) >= 3.0 and t >= 10.0:
        cooled = (t1 - t0) / (ts - t0)
        thermal = infer_share(removed_fraction=cooled, rate=before["rate"], minutes=t, minimum=THERMAL_SHARE_MIN)
        if thermal is None:
            thermal = THERMAL_SHARE_MIN  # the room did not follow the outdoor air at all (heating, sun)
        r_state["thermal_share"] = vote(r_state["thermal_share"], thermal, THERMAL_SHARE_PRIOR, weight, log(before["thermal_share"] / THERMAL_SHARE_PRIOR))
        h_state["thermal_share"] = vote(h_state["thermal_share"], thermal, THERMAL_SHARE_PRIOR, house_weight, offset(h_state["thermal_share"], HOUSE_PRIOR_WEIGHT))
        report["observed_thermal_share"] = round(thermal, 4)
    after = parameters(r_state, h_state, key, base_rate)
    report.update({"rate_after": after["rate"], "moisture_share_after": after["moisture_share"],
                   "thermal_share_after": after["thermal_share"], "rollback": bool(r_state["score"]["rollback"])})
    return r_state, h_state, report


# ------------------------------------------------------------------------------------------------ forecast quality

def update_score(score: Any, predicted_ml: float, observed_ml: float, reference_ml: float | None,
                 model_ml: float | None = None) -> dict[str, Any]:
    """Prequential score of one airing: running errors, the interval quantile and the rollback guard.

    ``predicted_ml`` is the forecast that was shown (interval calibration); ``model_ml`` the learned model's own
    forecast when another one was in force (physics fallback, rollback) – the error and the rollback guard follow it.

    The quantile follows online (adaptive) conformal calibration: it rises after a miss and falls after a hit so the
    long-run share of airings inside the interval approaches ``INTERVAL_COVERAGE``. That is a statement about many
    airings over time, not a probability for a single forecast.
    """
    s = {**new_score(), **(score if isinstance(score, dict) else {})}
    n = int(_num(s.get("n")) or 0)
    quantile = _clamp(_num(s.get("quantile")) or 1.0, 0.05, 3.0)
    error = abs(observed_ml - predicted_ml)
    normalised = error / max(abs(predicted_ml), SCORE_FLOOR_ML)
    if model_ml is not None:
        error = abs(observed_ml - model_ml)
    missed = normalised > quantile
    quantile = _clamp(quantile + 0.3 * max(quantile, 0.25) * ((1.0 if missed else 0.0) - (1.0 - INTERVAL_COVERAGE)), 0.05, 3.0)
    alpha = 1.0 if n == 0 else 0.2

    def blend(old: Any, new: float) -> float:
        previous = _num(old)
        return round(new if previous is None else previous * (1.0 - alpha) + new * alpha, 2)

    s["error_ml"] = blend(s.get("error_ml"), error)
    if reference_ml is not None:
        s["reference_error_ml"] = blend(s.get("reference_error_ml"), abs(observed_ml - reference_ml))
    s["n"], s["quantile"], s["covered"] = n + 1, round(quantile, 4), int(_num(s.get("covered")) or 0) + (0 if missed else 1)
    ours, theirs = _num(s.get("error_ml")), _num(s.get("reference_error_ml"))
    if ours is not None and theirs is not None and s["n"] >= ROLLBACK_MIN_SCORED:
        if ours > theirs * ROLLBACK_FACTOR + ROLLBACK_MARGIN_ML:
            s["rollback"] = True
        elif ours <= theirs * ROLLBACK_RECOVER_FACTOR:
            s["rollback"] = False
    return s


def forecast_quality(room: Any, predicted_ml: Any) -> dict[str, Any]:
    """What is known about the forecast error of this room – an interval only once it is calibrated."""
    score = _state(room, new_room_state())["score"]
    n = int(_num(score.get("n")) or 0)
    out: dict[str, Any] = {"model": MODEL, "scored_airings": n, "state": "calibrated" if n >= INTERVAL_MIN_SCORED else "collecting",
                           "coverage_target_percent": round(INTERVAL_COVERAGE * 100), "interval_ml": None,
                           "observed_coverage_percent": round(int(_num(score.get("covered")) or 0) / n * 100) if n else None,
                           "mean_error_ml": score.get("error_ml"), "rollback": bool(score.get("rollback"))}
    value = _num(predicted_ml)
    if n >= INTERVAL_MIN_SCORED and value is not None:
        half = _clamp(_num(score.get("quantile")) or 1.0, 0.05, 3.0) * max(abs(value), SCORE_FLOOR_ML)
        out["interval_ml"] = [round(value - half), round(value + half)]
    return out


# ------------------------------------------------------------------------------------------------ published fields

def room_fields(params: Any, room_state_value: Any, dynamic: Any) -> dict[str, Any]:
    """Additive room payload: the separate forecast quantities, their quality and the parameters in force."""
    forecast = dynamic if isinstance(dynamic, dict) else {}
    p = params if isinstance(params, dict) else {}
    net = forecast.get("net_room_change_ml")
    quality = forecast_quality(room_state_value, net) if p.get("active") else {"model": MODEL, "state": "not_applicable", "scored_airings": 0, "interval_ml": None}
    return {
        "forecast_net_room_change_ml": net,
        "forecast_outdoor_transport_ml": forecast.get("outdoor_transport_ml"),
        "forecast_to_target_ml": forecast.get("to_target_ml"),
        "forecast_interval_ml": quality.get("interval_ml"),
        "forecast_quality": quality,
        "iq2": {"model": MODEL, "active": bool(p.get("active")), "level": p.get("level"), "mode": p.get("mode"),
                "rate_per_min": p.get("rate"), "moisture_air_share": p.get("moisture_share"),
                "thermal_air_share": p.get("thermal_share"), "room_airings": p.get("room_airings", 0)},
    }


def house_fields(rooms: Any) -> dict[str, Any]:
    """House sums of the separate forecast quantities over the rooms that are aired right now (None without one)."""
    active = [r for r in (rooms.values() if isinstance(rooms, dict) else []) if isinstance(r, dict)
              and r.get("calculation_enabled", True) and r.get("data_quality") == "ok" and r.get("active")
              and not r.get("session_finalization_pending") and _num(r.get("forecast_net_room_change_ml")) is not None]
    if not active:
        return {"forecast_net_room_change_ml": None, "forecast_outdoor_transport_ml": None, "forecast_to_target_ml": None,
                "forecast_interval_ml": None, "forecast_quality_state": None, "forecast_scored_airings": None}
    targets = [_num(r.get("forecast_to_target_ml")) for r in active]
    intervals = [r.get("forecast_interval_ml") for r in active]
    calibrated = all(isinstance(i, list) and len(i) == 2 for i in intervals)
    return {
        "forecast_net_room_change_ml": round(sum(_num(r.get("forecast_net_room_change_ml")) or 0.0 for r in active)),
        "forecast_outdoor_transport_ml": round(sum(_num(r.get("forecast_outdoor_transport_ml")) or 0.0 for r in active)),
        "forecast_to_target_ml": round(sum(t for t in targets if t is not None)) if any(t is not None for t in targets) else None,
        "forecast_interval_ml": [round(sum(i[0] for i in intervals)), round(sum(i[1] for i in intervals))] if calibrated else None,
        "forecast_quality_state": "calibrated" if calibrated else "collecting",
        "forecast_scored_airings": min(int(_num((r.get("forecast_quality") or {}).get("scored_airings")) or 0) for r in active),
    }
