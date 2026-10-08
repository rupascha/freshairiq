# FreshAirIQ 0.25.2.20

## Recommendation Issuance Counter Hotfix

- Counts a recommendation opportunity immediately when a new recommendation episode is issued.
- Keeps repeated coordinator refreshes inside the same episode without duplicate counting.
- Finalization records followed/missed outcome without incrementing the opportunity a second time.
- No changes to ventilation decisions, three-state/mixed-source handling, learning or forecasts.
