# FreshAirIQ 0.26.0

Public feature release consolidating the development since v0.25.3.3.

## Recommendations and decision logic
- Multi-goal ventilation decisions coordinate dehumidification, CO₂ and temperature comfort instead of treating each goal as an isolated recommendation.
- Normal ventilation now evaluates meaningful house-wide benefit before falling back to a non-critical single-room recommendation. Critical mould/CO₂ protection remains room-specific and can override house optimisation.
- Per-room goal priorities remain explicit and are used to resolve competing goals without turning the highest-priority goal into an automatic room winner.
- Cross-ventilation, forecast/protection and existing safety behaviour remain part of the recommendation context.

## Learning and ventilation types
- Mechanical exhaust is a first-class ventilation session with isolated learning.
- Learning remains separated for fully open, tilted, cross-ventilation and mechanical-exhaust sessions; mixed sessions are quarantined from clean model samples.
- Multi-sensor room learning/recovery remains tolerant of unavailable redundant sensors while preserving conservative freshness and measurement gates.
- Roller shutters/blinds use configurable position interpretation. Up to and including 20% closed remains a normal learning sample; above the threshold the ventilation is still detected and balanced but excluded from normal learning with an explainable restriction reason.

## Room configuration and sensors
- CO₂ sensor, exhaust fan/mechanical ventilation and thermostat/climate configuration are first-class room options.
- Comfort target, manual target and fallback target temperatures are documented and supported without requiring a thermostat.
- Multiple temperature/humidity sensors per room and independent aggregation remain supported.
- Optional entity fields can be cleared persistently instead of being restored by schema defaults.
- Window/door reference temperature and humidity, opening delay, orientation and roller-shutter/blind configuration are grouped per opening.
- Roller-shutter position semantics can be configured for devices where 0% or 100% represents closed.
- Passive/imported rooms no longer require invented geometry, and obsolete room-wide reference-air writes are avoided.

## Configuration and usability
- Integration settings were consolidated under Devices & Services → FreshAirIQ → Configure; dashboard configuration remains presentation-focused.
- Recommendation-related settings are grouped, room priorities use an unambiguous ordered control, and duplicate priorities are rejected instead of silently reordered.
- Resident/profile configuration and comma-separated resident-name entry are explained more clearly.
- German room creation/import/edit flows include localized labels and help for CO₂, mechanical exhaust, climate and temperature-target settings, with matching English coverage.
- Contact-related opening delay and orientation were moved into the respective window/door configuration.
- The optional room section is named “Optional additional sensors” / “Optionale Zusatzsensoren” because reference sensors now belong to individual openings.

## Dashboard, support and ventilation log
- Live mechanical ventilation is shown explicitly in the moisture balance.
- The ventilation PDF was made more compact and table-oriented while preserving local logging and export behaviour.
- Details/support mobile layout, typography and contrast were polished.
- The support area keeps diagnostics/feedback separate from the canonical integration settings.
- Anonymous installation heartbeat remains independent from optional nightly diagnostic sharing; disabling diagnostic sharing does not transmit diagnostic payloads.

## Reliability and compatibility
- Existing single-sensor and legacy room configurations remain supported through migration/compatibility paths.
- Room edits refresh source listeners/coordinator state without unnecessarily reloading the complete integration; structural room add/remove operations retain the required reload behaviour.
- Performance/release gates, migration/golden scenarios and configuration contracts were extended alongside the new behaviour.

This release intentionally promotes the internally validated v0.25.4.19 release-candidate code to v0.26.0; no additional recommendation/runtime feature change is introduced by the version bump itself.
