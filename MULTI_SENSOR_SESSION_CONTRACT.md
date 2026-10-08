# Multi-Sensor Session Measurement Contract — v0.25.3

This is a release invariant.

- Live room climate uses all currently valid configured sensors.
- A ventilation-session measurement is not released until at least one logical climate sensor independently supplies two fresh reports after session start.
- Valid two-report combinations are: 2× temperature, 2× humidity, or 1× temperature + 1× humidity.
- Reports from different sensors must never be added together to satisfy this base condition.
- After the base condition is satisfied by one sensor, additional available sensors with at least one fresh report may participate in the session aggregation.
- A sensor with zero fresh reports does not participate in the session measurement.
- An unavailable redundant sensor does not block the room or the measurement gate.
- Mean/min/max remains the room-specific aggregation policy for the qualified participating sensors.
