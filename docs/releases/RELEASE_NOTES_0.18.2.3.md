# FreshAirIQ v0.18.2.3

Hotfix based on v0.18.2.2.

- Correct diagnostic learning-store key mapping (`learning_rate`, `learning_samples`, `diagnosis`).
- Restore complete room payload in the central status entity as a safe history fallback while retaining per-room transport.
- Add stable FreshAirIQ identity metadata to status/control entities and prefer current `status_v2`/version over stale registry states.
- Bind operating-profile and forecast-horizon controls only to FreshAirIQ-tagged entities, with a restricted legacy fallback.
- No changes to the physical ventilation, mould, forecast or wall/reference-air model.
