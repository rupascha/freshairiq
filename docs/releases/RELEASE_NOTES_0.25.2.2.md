# FreshAirIQ 0.25.2.2

## Guardian Incident Lifecycle Hotfix

- Guardian incidents now distinguish current failures from recovered historical findings.
- Two consecutive healthy Guardian evaluations are required before an incident is marked resolved.
- Historical occurrence counts and timestamps remain available for diagnostics.
- A later recurrence reopens the same incident immediately.
- Resolved Guardian history no longer keeps the runtime-health error state or error-upload fingerprint active.
- Ventilation physics, sensor-recovery decisions, recommendation decisions, learning and user configuration are unchanged.
