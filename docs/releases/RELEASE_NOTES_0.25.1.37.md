# FreshAirIQ v0.25.1.37 — Delayed Room Commit Hotfix

- Fixes native room creation when Home Assistant commits the new room subentry later than the first event-loop turn.
- FreshAirIQ now waits for the observable Home Assistant room-subentry commit for a short bounded period before synchronizing canonical parent room data.
- Failed Home Assistant room flows remain atomic: without a committed subentry, no parent room is written and no reload is scheduled.
- Existing room, ventilation, forecast, learning, recommendation and dashboard behavior is unchanged.
