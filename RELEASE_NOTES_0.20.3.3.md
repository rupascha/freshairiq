# FreshAirIQ 0.20.3.3 — Measurement Frames v1

This release adds temporal sensor coherence checks without changing the physical forecast model. Every room cycle now evaluates how closely temperature, relative humidity and reference-air reports align in time.

## Quality classes

- **Excellent:** <=30 s temporal skew between paired measurements.
- **Acceptable:** <=90 s temporal skew.
- **Uncertain:** <=180 s skew; kept for live operation but excluded from learning/validation.
- **Stale:** missing timestamps, excessive skew or stale inputs; excluded from learning/validation.

Start and end frames must both be sufficiently coherent before a ventilation session can update the learned air-exchange model. Frozen start forecasts and final measurements must also have valid frames before they are scored by the Validation/Backtest Engine.

Diagnostics schema is now version 6 and includes per-sensor age, frame skew and frame quality.
