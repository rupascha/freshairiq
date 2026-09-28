# FreshAirIQ 0.25.1.35 — Room Creation Race Hotfix

## Fixed
- Fixed a race in native Home Assistant room creation where FreshAirIQ could reload the parent config entry before Home Assistant had committed the new room subentry.
- The premature reload could mirror the room from canonical parent data and then collide with the still-running subentry flow using the same room unique ID.
- The structural reload is now deferred to the next event-loop turn so Home Assistant can finalize the room subentry first.

## Compatibility
- Existing rooms and room data remain unchanged.
- No ventilation, forecast, learning, recommendation or dashboard logic changed.
