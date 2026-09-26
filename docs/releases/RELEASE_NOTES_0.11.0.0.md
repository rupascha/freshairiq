# FreshAirIQ v0.11.0.0 – Self-Learning Live Ventilation Coach

Phase 7 continuously re-evaluates a running ventilation session.

- Compares actual moisture removal with the trajectory predicted when the recommendation was followed.
- Can shorten the target when ventilation is performing faster than expected.
- Can cautiously extend the target when performance is slower but another air exchange remains useful.
- Uses real outcome-feedback samples and forecast confidence to limit adaptation strength.
- Recomputes the remaining time live.
- Uses marginal 5-minute moisture benefit and temperature effect to identify the efficient closing point.
- Existing physical close criteria, mould/CO₂ urgency and configured min/max durations remain authoritative.
- The dashboard reuses the existing ventilation-time metric; no new large card is added.
