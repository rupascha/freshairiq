# FreshAirIQ 0.25.2.18

## Mixed opening provenance & recommendation telemetry hotfix

- Keeps recommendations unchanged for both two-state and three-state contacts.
- Uses tilt/open specialist forecast models only when every active opening has unambiguous proven three-state provenance.
- Mixed active two-state + three-state openings and mixed tilt + open states fall back to the established general room model.
- A source change during a running session prevents that session from contaminating a specialist opening model.
- Adds privacy-safe `mixed_source_session` evidence to nightly three-state learning diagnostics.
- Fixes recommendation reach telemetry by exporting the persistent recommendation counters that FreshAirIQ actually learns.
- Adds `recommendation_opportunity_count` to the nightly transport summary while preserving completed/followed counts separately.
