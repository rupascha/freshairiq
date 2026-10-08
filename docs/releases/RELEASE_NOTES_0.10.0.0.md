# FreshAirIQ v0.10.0.0 – Self-Optimising Ventilation Strategy

Phase 6 adds per-decision ventilation-duration optimisation.

- Simulates minute-by-minute durations within the configured min/max range.
- Uses learned room exchange rate and real outcome feedback calibration.
- Chooses the shortest near-optimal duration to avoid unnecessary heat loss.
- Calculates the marginal benefit of another 5 minutes.
- Optimises duration separately for now and for future-weather options.
- User strategy remains subordinate to health, mould/CO₂ and physical constraints.
- Existing v0.9.9.0 behaviour remains the fallback.
