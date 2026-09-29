# FreshAirIQ v0.25.1.38 — Room Creation Trace Hotfix

## Changed
- Adds privacy-safe diagnostic trace events for room creation through the native Home Assistant room subentry flow, the FreshAirIQ options flow, and the dashboard settings API.
- Records canonical parent-room and native room-subentry counts/fingerprints before and after the relevant commit stages.
- Records whether Home Assistant's native room subentry commit is observed or times out in the existing bounded post-commit synchronizer.
- Captures a delayed post-reload state so a room that is accepted and then lost during reload can be distinguished from a room that was never committed.
- Validation failures record only error keys/type; room names, entity IDs, raw form payloads, and exception messages are not added to the trace.

## Behaviour
- No room persistence, validation, ventilation, forecast, learning, notification, or recommendation logic is changed by this hotfix.
