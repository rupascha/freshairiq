# FreshAirIQ 0.23.0.2

Hotfix focused on configuration reliability and the requested ventilation/configuration corrections.

- One canonical resident profile/settings page.
- Per-opening reference temperature + humidity pairs for windows/doors; conservative handling of multiple simultaneous air sources.
- Clearer reference-sensor explanations in dashboard and native Home Assistant configuration.
- Dynamic room → floor ventilation reassessment.
- Stronger repeat-recommendation cooldown after completed ventilation.
- No user-facing internal decision score.
- IQ Aktiv explicitly describes what is currently being learned.
- Low-cadence battery sensors may contribute cautiously to adaptive room learning; objective forecast validation still requires synchronized frames.
- Canonical room order used across payloads and views.
- Early synchronous public custom-element registration plus single resource-registration path to reduce Home Assistant/iOS/iPadOS cold-load Configuration Error races.
