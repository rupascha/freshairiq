# FreshAirIQ 0.1.0 — technical preview

This is the first installable community port of the V14.2.1 Home Assistant package.

## Ready for testing
- generic UI setup
- arbitrary room count
- absolute humidity and moisture potential
- per-room alternative reference air
- live ventilation sessions
- next-five-minute yield and temperature-cost close logic
- estimated surface humidity / mould level
- persistent adaptive learning
- optional room CO₂
- cross-ventilation pairs
- German / English setup

## Intentionally beta
The original household-specific notification routing, presence rules, winter-garden door warning and 4-hour weather recommendation are **not hard-coded into the integration**. They depend on household entities and are better represented as optional automations/features after the calculation core has been validated against real V14.2.1 sessions.

Do not disable a working V14.2.1 package on the first test. Run both in parallel and compare several sessions.
