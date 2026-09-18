# FreshAirIQ v0.9.4.1 – Hotfix

This release is a focused hotfix on top of v0.9.4. No feature redesigns or recommendation/model changes were made.

## Fixed

- Status sensor no longer fails when no house-level temperature history exists.
- Persisted ventilation sessions survive Home Assistant startup ordering when climate sensors are temporarily unavailable.
- Dashboard metrics use the already-resolved FreshAirIQ status payload first, reducing wrong zero values from stale or suffixed entity IDs.
- Frontend no longer modifies Home Assistant state attributes in place.
- Reset statistics now also clears daily water history and the last-ventilation summary.
- Notification cooldown is recorded only after an available notify service is called.
- Device/software/frontend version metadata is synchronized to 0.9.4.1.
- Missing forecast sensor translation keys were added.
