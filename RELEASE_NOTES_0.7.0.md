# FreshAirIQ 0.7.0 — Ten-point intelligence & UX update

This release implements the ten requested FreshAirIQ corrections and extensions on top of 0.6.3.

1. **Night forecast:** occupant counts remain part of the physical prior. When ventilation contacts are currently open, local outdoor temperature/humidity plus wind/orientation now modify the overnight moisture forecast.
2. **Unified recommendations:** one priority-based room recommendation layer combines sensor validity, active ventilation, moisture, thermal/cooling benefit, wind/orientation and pollen. Pollen is evaluated only when pollen mode is enabled.
3. **Reasons:** every room recommendation exposes a human-readable reason list in addition to the action.
4. **Visual dashboard editor:** the custom card now provides a Home Assistant visual editor for showing/hiding temperature, ventilation time, 5-minute forecast, night forecast, mould risk and the details button.
5. **Detail scrolling:** the modal explicitly supports touch/pointer vertical scrolling across the full content area and prevents parent-card gesture capture.
6. **Measurement timestamps:** each room shows the last measurement time. Valid measurements are subtly green; invalid measurements subtly red. Learning measurements carry their own timestamp and validity state.
7. **Room drill-down:** tapping a room opens a detailed room view with current climate, recommendation reasoning, window directions, airflow, IQ model and room-specific 14-day moisture/temperature/session statistics.
8. **Restart continuity:** running ventilation sessions persist their latest live balance. On the first valid update after restart, the moisture baseline is re-based while preserving the accumulated balance, avoiding jumps caused by sensor restore order or changed reference data.
9. **Visible defaults:** option labels/descriptions show documented defaults where applicable. A new **Reset all settings to defaults** action restores `DEFAULT_OPTIONS` without deleting rooms, sensors or statistics.
10. **Per-window orientation during room setup:** the old room-wide orientation field and separate orientation menu are removed from the normal workflow. After selecting a room's contacts, FreshAirIQ immediately asks for the direction of each individual window/door.

Additional changes: integration/config-entry schema is version 7, frontend cache/version metadata is 0.7.0, and persistent storage now keeps room-level history and temperature points.
