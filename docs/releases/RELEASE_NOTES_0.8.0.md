# FreshAirIQ 0.8.0

## Native room UX, robust sessions and profile intelligence

This release is the first FreshAirIQ version in which room configuration is modelled as a native Home Assistant subentry. It separates global integration settings from room-local settings and removes the need to hunt through one large options tree for sensor or window changes.

### Implemented

- **Room-local configuration:** each room is a Home Assistant config subentry. Open the room to edit temperature/humidity/CO₂ sensors, volume/dimensions, user-defined floor/zone, contacts, per-contact compass direction and opening delay.
- **Global settings remain global:** outdoor source, operating mode, dwelling profile, occupants, pollen/wind, energy, notifications, statistics and expert model parameters remain on the FreshAirIQ parent entry.
- **Room ordering:** reorder-capable Home Assistant selector is used for room and level order.
- **Free floors/zones:** no hard-coded basement/ground/attic assumption. Users can create labels such as Zwischenebene, Wintergarten, Anbau or Außenbereich.
- **Expanded dwelling profile:** detached, semi-detached, mid/end terrace, apartment, maisonette and multi-family building are stored for future model segmentation without pretending that building type alone determines wall physics.
- **Separate drill-down dialogs:** room details and live mL breakdown no longer appear at the top of the main details panel.
- **Scroll behaviour:** touch/momentum gestures are not intercepted; live DOM replacement is deferred during active scrolling and repeated delayed scroll-position writes were removed.
- **Mould display:** main tile shows the verbal risk class only. Detailed surface-RH estimates remain available in room details.
- **Operating mode:** dashboard mode pill is clickable, explains all profiles and changes the native FreshAirIQ profile select.
- **Mode-specific recommendations:** Dehumidify, Comfort and Summer Cooling have different start/continue/close priorities; absolute-humidity, surface-RH and energy calculations stay common.
- **Restart continuity:** active sessions keep their original window-open absolute-humidity baseline. The live result is persisted as a fallback during startup, then current measurements continue against the original baseline.
- **House-status priority:** Close outranks generic Ventilation running.
- **Statistics reset:** clears house and per-room statistics.
- **Time handling:** Home Assistant local time is used consistently for day windows.
- **Pollen consistency:** house and room logic use the same strict-veto/urgent-override semantics.
- **Testing:** CI runs compileall, JavaScript syntax checking and pytest with Home Assistant installed. Pure calculation tests cover psychrometrics, learning, energy, night forecasting, restart continuity and profile-specific behaviour.

### Validation status

The package passes Python compilation, JavaScript syntax checking, JSON/YAML parsing and 16 pure calculation tests in the build environment. The GitHub workflow additionally installs Home Assistant and executes the normal package imports. Before calling the release fully stable, perform one real-device restart test while a ventilation session is active and verify that the displayed mL value continues rather than returning to zero.
