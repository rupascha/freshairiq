# FreshAirIQ 0.20.5.0

- Dashboard card is recommendation-first: supplemental dashboard toggles and fixed header/process blocks are hidden.
- Settings navigation reduced to seven clear top-level groups without removing existing settings.
- Resident profiles can assign personal notify/mobile-app targets; house recommendations are worded per assigned resident/device.
- Structural rooms without climate sensors can be stored when climate calculations are disabled; room volume and floor remain part of the building structure without inventing climate measurements.
- Active moisture sources such as cooking override a normal close recommendation while reference air is still useful.
- Long, thermally stable open-window sessions transition to a monitored probable tilt/permanent-opening state instead of pinning the main recommendation on “close”.
- Recommendation scope now distinguishes room, floor and house; same-floor multi-room actions are labelled as floor ventilation.
- Frontend status transport no longer rejects a valid backend payload solely because an iPad/phone still has the immediately previous frontend version cached.
- Regression suite updated for the new release contract.
