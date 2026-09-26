# FreshAirIQ 0.24.14.0

## Optional sensor, settings-parity and frictionless-setup update

This release keeps the established ventilation physics, forecast coefficients, learning rates and canonical recommendation thresholds unchanged. It improves how the post-0.23 optional sensors and configuration surfaces are presented and controlled.

### Optional VOC/TVOC, PM2.5 and illuminance sensors
- VOC/TVOC, PM2.5 and illuminance are explicitly marked as optional in both Devices & Services and the dashboard settings.
- The explanations state that these sensors do **not** change the canonical humidity/ventilation physics, ml forecast or learning model.
- When enabled and configured they may enrich supplemental recommendations, such as air-purifier or shading suggestions.
- Each sensor type has a global enable/disable switch. Disabling a type stops FreshAirIQ from subscribing to, reading, displaying or using that sensor type for supplemental recommendations while preserving the room assignment.
- The general dashboard-card editor exposes the same three global enable/disable controls, and also allows the optional sensor information rows to be hidden per card.

### Settings parity and cleanup
- Devices & Services and the dashboard gear edit the same ConfigEntry data/options rather than maintaining a second settings store.
- Building information is separated from the resident profile, and the previous duplicated resident/presence/personalisation exposure is removed from the normal navigation.
- Resident, presence, comfort, night and personal-device/profile settings are consolidated into one resident section.
- The new optional sensor switches and thresholds are available through both settings surfaces.
- German labels, descriptions, defaults and examples were expanded for the new settings; matching English translation keys are retained for Home Assistant translation integrity.
- Dashboard settings categories retain explicit Material Design icons, and collapsible native Devices & Services sections now receive matching section icons where Home Assistant supports them.

### Frictionless first installation
- FreshAirIQ can now be added without configuring a room first.
- Outdoor weather/temperature/humidity can also be completed after installation.
- A manually configured outdoor temperature/humidity source must still be supplied as a complete pair.
- Empty installations remain valid so the integration and dashboard can be created first, then rooms and advanced settings can be added afterwards.

### Diagnostics / beta data
- Diagnostics schema is now **9**.
- VOC/TVOC, PM2.5 and illuminance values, availability, enable state and configured state are exported per room.
- The compact 30-day trend trace also carries these optional-sensor fields.
- The configuration snapshot reports how many rooms have each optional sensor type configured.
- Disabled optional sensor types are represented as disabled rather than silently affecting recommendations.

### Compatibility / calculation safety
- No intended change to the canonical ventilation physics, absolute-humidity calculation, forecast model, learning coefficients or core decision thresholds.
- Changes are limited to configuration, optional-sensor gating, supplemental intervention inputs, diagnostics and presentation.

### Verification
- Python compilation, JSON parsing and JavaScript syntax checks are part of the release verification.
- The local pure-logic regression suite is run before packaging (514 tests; 95.06% measured pure-logic coverage in the final worktree).
- Home Assistant runtime tests remain covered by the project CI environment when the local offline environment does not provide the `homeassistant` test package.
