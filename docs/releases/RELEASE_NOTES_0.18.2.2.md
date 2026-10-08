# FreshAirIQ v0.18.2.2

Hotfix release based on v0.18.2.1.

## Fixed
- CO₂ sensors that are unavailable/unknown are no longer converted to a false 0 ppm measurement. CO₂ availability is propagated consistently through room evaluation, recommendation, live-coach, planner and decision layers.
- Completed ventilation sessions keep their signed physical moisture balance. Positive values mean moisture removed; negative values mean moisture added.
- Outcome feedback and house-strategy learning now retain negative ventilation outcomes instead of flattening them to zero.
- Notifications, last-ventilation display and room history correctly distinguish moisture removal from moisture ingress.
- Per-room history and temperature history now use the configured 1–30 day statistics period instead of a hard-coded 14-day window.
- Central status attributes no longer duplicate the large per-room history arrays. The dashboard merges full room payloads from the existing room transport entities.
- Diagnostic exports are protected by a 24 MB decoded payload cap to reduce browser memory pressure; if truncation is necessary, the newest retained records are preferred.

## Verification
- 68 automated tests pass.
- All Python sources compile and parse successfully.
- JSON resources validate.
- Example YAML files parse successfully.
- Dashboard JavaScript passes syntax validation.
