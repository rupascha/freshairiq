# FreshAirIQ v0.25.0.2 – Reliability & Diagnostics Hardening

- Sensor-frame quality now caps forecast confidence. Stale frames cannot appear high-confidence; held/uncertain frames are conservative.
- Faulty rooms are isolated; a house-wide sensor error is emitted only when no valid calculable room remains.
- Recommendation/action state changes are stored as compact decision events. Completed sessions, window events and configuration changes retain full diagnostic fidelity, protecting the 30-day field-test window from premature export truncation.
- Existing absolute-humidity physics, room thresholds, reference-climate selection, learning rejection rules and close/continue physics are intentionally unchanged.
- Version synchronized across backend, manifest and frontend assets.

## Noch offene v1-Gates

Die in `QUALITY_GATES_1.0.md` dokumentierte reale Home-Assistant-Runtime-Coverage bleibt offen. Dieser Hardening-Stand ersetzt keine noch ausstehenden Tests auf einer vollständigen Home-Assistant-Testumgebung.
Damit ist v0.25.0.2 ausdrücklich **kein** 1.0-Release.
