# FreshAirIQ 0.20.3.5 — Forecast Quality & Learning Components

This release makes learning and forecast quality transparent without retuning the forecast model.

## New
- Backtest Engine v2 adds guarded model reliability with separate empirical quality and evidence maturity.
- Room-level reliability summaries are available for diagnostics and UI use.
- The Details window includes a new component learning-status card showing each adaptive subsystem independently.
- Learning component state is exported through the status/diagnostics transport (schema 8).

## Unchanged
- Live forecast physics
- Recommendation thresholds and safety rules
- Adaptive learning coefficients
