# FreshAirIQ v0.25.1.40 — Contactless Indoor Model Parity Hardening

## Changed
- Promotes the contactless indoor/passive-learning architecture to v0.25.1.40.
- Adds an explicit physics parity regression matrix for own-opening, assigned-opening and contactless indoor-room configurations.
- Locks absolute humidity, water-in-air, humidity delta, theoretical moisture potential, surface humidity and mould classification to identical results when climate inputs are identical.
- Separately verifies that only ventilation-path-dependent behavior may differ.

## Compatibility
Existing rooms with own openings, assigned openings and monitor/reference rooms remain supported.

### Additional regression hardening
- Added a SHA-256-pinned v0.25.1.38 physics Golden Master with 81 reference climate cases.
- v0.25.1.40 must reproduce the v0.25.1.38 thermodynamic outputs for unchanged physics.
- Added dynamic dry→wet and wet→dry weather-reversal tests across own-opening, assigned-opening and contactless room paths.
- A mid-session loss of the drying advantage is now sticky evidence contamination: the moisture balance remains measurable, but adaptive ventilation-rate and forecast-outcome learning are skipped for that session.
