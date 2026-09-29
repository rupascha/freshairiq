# FreshAirIQ v0.25.1.39 — Room Sensor Activation & Dashboard Strategy Hotfix

- Sensorless planning rooms now retain an internal auto-passive marker and automatically enter calculations when a complete temperature, humidity and opening-contact setup is added later.
- Rooms that were explicitly disabled after already having sensors remain disabled.
- The automatically generated FreshAirIQ dashboard now exposes the Classic/FreshAirIQ IQ style selector and propagates the selected variant to the generated card.
- Existing room-creation tracing and delayed/atomic commit safeguards remain unchanged.
