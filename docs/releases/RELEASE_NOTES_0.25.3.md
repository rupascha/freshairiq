# FreshAirIQ v0.25.3

## Local ventilation log and PDF export

- Adds a local, persistent ventilation log for completed room ventilation sessions.
- Adds selectable date-range PDF export in the FreshAirIQ details view.
- Reports room name, start/end time, duration, recommendation-follow status and, when sensor evidence is valid, temperature, relative/absolute humidity and measured moisture balance.
- Keeps the log inside Home Assistant; it is not part of support telemetry.
- Retains up to 730 days / 10,000 completed sessions.
- The PDF explicitly documents sensor observations and does not claim a legal determination of correct ventilation.
- Includes all fixes and compatibility work from v0.25.2.29 through v0.25.2.39.
