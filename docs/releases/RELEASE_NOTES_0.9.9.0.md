# FreshAirIQ v0.9.9.0 – Adaptive User Strategy

Phase 5 adds a conservative strategy-learning layer on top of the working v0.9.8.0 intelligence stack.

## Added
- Learns which recommendation styles are actually followed (`now`, `wait_15`, `wait_30`, `wait_60`, night) combined with short/medium/long recommended duration.
- Separately learns whether followed recommendations achieved at least 70% of their predicted moisture removal.
- Uses Bayesian-style neutral priors and maturity gates so sparse history cannot dominate decisions.
- Decision Engine may use strategy fit only to refine similarly good choices; influence falls to zero under high health pressure.
- Simulation details can show learned implementation probability for sufficiently mature options.
- Room details expose compact Strategy-IQ maturity and sample counts.
- IQ activity can report `Nutzerstrategie optimiert` once the model is mature enough.

## Safety / compatibility
- Existing v0.9.8.0 room physics, routines, weather, forecast and outcome feedback remain intact.
- Real-time states and health priorities remain authoritative.
- Existing storage is migrated lazily through default fields; no reset of learned values is required.
