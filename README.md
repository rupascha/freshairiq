# FreshAirIQ

![FreshAirIQ branding](docs/freshairiq-branding-official.png)

**Intelligent lüften. Gesund wohnen. Energie sparen.**

FreshAirIQ is a Home Assistant custom integration developed by **rupascha**. The current release combines the proven calculation principles with a dynamic room model, persistent learning, live forecasts, the adaptive dashboard card, the Continuous Quality System and the authenticated local staging connection to the FreshAirIQ Diagnostics Hub.


## Current release: 0.25.0.40 – GitHub Release Gate


- **Mess-/Lernlogik eingefroren:** Timestamp-Gate, 0,75/1,0-Gewichtung, Feuchtephysik, Forecast-Formeln und Lernformeln bleiben gegenüber 0.25.0.33 unverändert.
- **Fehlender Abschluss-Refresh verwirft keine gültige Lüftung:** antworten die Sensoren nach dem letzten Schließen nicht erneut, bleibt der zuletzt vorhandene numerische Zustand verwendbar; die Session behält ihre bereits nachgewiesene In-Session-Evidenz.
- **Deterministischer 10-s-Failsafe:** wird ein Klimasensor beim Ablauf der Abschlusswartezeit tatsächlich `unavailable`, wird zuerst der letzte gültige numerische Zustand derselben laufenden Session verwendet. Dieser Fallback erzeugt keine neue Timestamp-Evidenz und kann den strikten Lern-Gate nicht umgehen.
- **Kein Endwert vorhanden:** nur wenn selbst innerhalb derselben Session kein nutzbarer numerischer Endzustand vorhanden ist, wird die Lüftung sauber als *nicht ausreichend gemessen* abgeschlossen – ohne erfundenen ml-Wert, ohne physikalisches Lernen, ohne Prognosekalibrierung und ohne vertrauenswürdige Endbaseline.
- **Diagnostics Privacy Hardening:** Bewohnernamen aus der realen kommagetrennten Konfiguration werden auch in Freitexten anonymisiert; echte IP-Adressen bleiben geschützt, während bekannte FreshAirIQ-Versionsfelder wie `0.25.0.34` nicht mehr fälschlich als IPv4 geschwärzt werden.
- **Diagnosezählung korrigiert:** `resident_profile_count` zählt Bewohner statt Zeichen im Namensstring.
- **Android-Test gehärtet:** der Android-WebView-Playwright-Test setzt nun einen echten Mobile-Viewport-Meta-Tag und verifiziert die tatsächliche CSS-Breite bei 360, 412, 600 und 800 px.
- **Abschlussbenachrichtigung korrekt:** nicht ausreichend gemessene Sessions melden keinen erfundenen Wert wie „0 ml entfernt“.
- **Diagnostics HA / Hub kompatibel:** Upload-Schema, Cursor-Schema, Diagnose-Schema, Enrollment-, Chunk-, Feedback- und Migrationspfade bleiben unverändert.

### Continuous Quality lokal

```bash
python tools/quality_gate.py --profile local
python tools/build_release.py
```

Die verbindlichen Grenzwerte liegen in `quality/quality_policy.json`; Performance-Baselines liegen in `quality/performance_baseline.json`.

## Highlights in 0.8.0

- Fully integrated `custom:freshairiq-card` with a live main tile and built-in details popup.
- Moisture convention in the UI: **minus/green = moisture removed**, **plus/red = moisture added**.
- Adaptive default ventilation threshold scaled to dwelling size and expected moisture generation, targeting roughly **3–5 meaningful ventilation cycles per day**; cool morning/evening opportunities are preferred in the warm season.
- Rooms can be assigned to floors, sorted, and kept visible as monitoring-only rooms without influencing calculations.
- Direct room volume **or** dimensions; dimensions are used when all three are supplied, otherwise the direct m³ value is used.
- Optional window orientation with conservative wind-dependent airflow correction from the configured weather entity.
- Optional pollen sensor and pollen veto for normal ventilation decisions; urgent mould/CO₂ cases remain visible instead of being silently suppressed.
- Individual opening delay for every configured contact sensor.
- Persistent per-room learning with visible sample count, learned air-exchange rate and last diagnosis. Learning changes its internal model values, not the user's threshold settings.
- Configurable learning maximum, default **120 min** instead of the former 45-minute ceiling.
- Occupant model uses adults and children as inputs; moisture production is an internal prior and is adapted by the whole-house night learner instead of being exposed as four manual moisture sliders.
- Night forecast appears directly on the main tile.
- Heating-cost model supports heat pumps, gas, heating oil, district heating and direct electric heating with system-specific inputs.
- Statistics period selectable from 1 to 30 days.
- Dehumidify, Comfort and Summer Cooling profiles expose profile-relevant parameters and explanations.


### 0.8.0 UX & reliability update

FreshAirIQ 0.8.0 turns every configured room into a native Home Assistant configuration subentry. Global settings stay on the FreshAirIQ parent entry, while room-specific sensors, zone, window directions and contact delays can be edited directly from the room entry. The global options flow remains for house-wide settings plus room add/remove/order and free building-zone management.

The dashboard now opens room details and the live moisture breakdown in separate overlays instead of injecting them into the top of the main details area. The main tile shows mould risk as a verbal level only. The operating profile is clickable, explained and switchable through the FreshAirIQ profile select entity. The details scroller no longer performs repeated delayed `scrollTop` writes; active touch/momentum gestures defer DOM refreshes instead.

Restart continuity now preserves the original absolute-humidity baseline of a running ventilation session. The persisted live mL value is a fallback while sensors restore, but once valid values return FreshAirIQ continues calculating against the original window-open baseline rather than resetting or silently rebasing the session.

House profiles now distinguish detached, semi-detached, mid/end terrace, apartment, maisonette and multi-family buildings. Floors/levels are user-defined labels and can be created, sorted and removed instead of assuming a particular house layout. Operating profiles have distinct priorities for dehumidification, comfort and summer cooling while the underlying psychrometric calculation remains common and physically consistent.

### 0.7.0 ten-point update

FreshAirIQ 0.7.0 adds weather-aware overnight forecasting for open windows, a single priority-based recommendation engine with explicit reasons, a visual Home Assistant card editor, full-area touch scrolling, timestamped measurement quality, detailed per-room 14-day statistics, restart-stable live balances, visible/resettable defaults, and per-window compass directions directly in room setup. See `RELEASE_NOTES_0.7.0.md` for the complete ten-point mapping.

### 0.6.3 correction pass

Version 0.6.3 builds on the restart/configuration hardening from 0.6.2 and completes the nine-point dashboard correction pass. A live ventilation balance is now calculated **only from currently active sessions**. Each newly opened session starts from a clean zero baseline, while valid recent sessions can continue across a Home Assistant restart. Persisted sessions with invalid, stale or legacy baselines are safely re-based once plausible sensor values are available; sessions that are already closed while climate sensors are unavailable are cancelled without feeding placeholder values into learning or statistics. This prevents extreme moisture and temperature values after startup.

The **Pollen & wind**, **Model parameters** and heating-system detail forms use Home Assistant-compatible numeric selectors, including dimensionless inputs such as pollen index, surface factor, COP and efficiency. The integrated details dialog persistently tracks its own scroll position and restores it after live entity updates and layout passes, so 30-second or sensor-triggered refreshes do not jump back to the top.




## Presence-aware Forecasts & Guest Mode (0.8.6)

FreshAirIQ can optionally use Home Assistant `person.*` or `device_tracker.*` entities for adult and child residents. Tracked residents who are away are removed from the live moisture-production prior immediately. Residents without a phone/tracker remain supported; by default they follow the overall household presence signal, which is useful for children without their own phones. Unknown/unavailable tracker states are handled probabilistically and lower the displayed presence confidence instead of producing a hard false home/away switch.

Two persistent number controls — **Übernachtungsgäste Erwachsene** and **Übernachtungsgäste Kinder** — provide a fast guest mode. The integrated card exposes a **Gäste** button with +/- controls. Any change immediately recalculates the configurable short-term forecast and the overnight forecast. Setting both guest counts back to zero effectively disables guest mode.

The overnight model is now occupancy-aware and uses the **remaining** night duration when the night has already started. It combines configured biological priors, a household-normalised learned night rate, current occupancy/guests, recent room moisture-source residuals, absolute outdoor humidity, actually open windows, learned air exchange, wind/orientation and cross-ventilation. The card reports a dedicated overnight confidence score plus weather and trend contributions in the detail explanation.

## Intelligent Forecast (0.8.5)

FreshAirIQ now provides a freely selectable 1–120 minute live forecast. The dashboard combines predicted moisture change (± ml), room-air temperature change (± °C), reheating cost (€) and a confidence score. The model blends learned air exchange and outside/reference air with recent **absolute-humidity** and temperature behaviour, internal moisture/source residuals, household moisture priors, cross ventilation, wind/orientation and heating-system energy data. Existing fixed 5-minute entities remain available for backwards compatibility.

## Recommendation Engine v2 (0.8.4)

The main card now presents **one prioritised action** instead of a list of competing room recommendations. FreshAirIQ first diagnoses every room, then scores viable actions using room humidity persistence/trend, surface-mould risk, CO₂, absolute-humidity delta, removable moisture, wind/orientation, learned air-exchange behaviour, temperature loss and estimated reheating cost. Configured cross-ventilation pairs can be preferred when they provide the best overall action. Room-level diagnostics remain available under **Räume**.

A genuinely problematic room can still trigger targeted ventilation below the house-wide threshold; if outdoor/reference air is unsuitable, the same engine explicitly recommends waiting and explains why.

## V14.2.1 calculation basis

FreshAirIQ keeps the central V14.2.1 principles: absolute humidity, per-room source-air comparison, adaptive RH/delta decisions, per-room moisture potential, learned air-exchange rates, next-five-minute yield, temperature-loss/efficiency checks, estimated cold-surface RH and cross-ventilation bonus.

The full-session moisture forecast now uses the same exponential replacement form as the supplied V14.2.1 YAML:

`fraction = 1 - (1 - effective_rate) ^ duration`

The default threshold is adaptive: FreshAirIQ combines expected daily moisture generation with the total water vapour in calculation-enabled rooms and targets roughly four meaningful ventilation opportunities per day. In the warm season, a cooler early-morning or evening outdoor-air window lowers the trigger conservatively. Percentage-of-water and fixed-mL modes remain available for advanced users.

### Nine-point dashboard correction pass

The main card now shows the current mould risk, explicitly warns **Nicht lüften** when reference/outdoor air would add moisture and quantifies the estimated five-minute moisture gain. In idle state the card is intentionally slimmer: temperature, ventilation time and the extra-five-minute forecast only appear while a ventilation session is active. Mould risk is colour-coded per room, every room shows its latest learning measurement, and Details contains a house-wide learning status with total samples and stable-room count. The remaining English idle text has been translated. Room-detail clicks preserve the current Details scroll position. Signed moisture effects are handled independently from non-negative removable potential so moisture ingress during an active session no longer causes the custom card to disappear. Legacy/out-of-range model and pollen settings are bounded before forms are rendered, preventing settings pages from failing with a configuration error.

## Installation via HACS (Beta / Custom Repository)

For beta testers, FreshAirIQ can be installed and updated through HACS as a custom integration repository. Add `https://github.com/rupascha/freshairiq` under **HACS → Custom repositories**, choose **Integration**, install **FreshAirIQ**, restart Home Assistant, and then add FreshAirIQ under **Settings → Devices & services**.

Published GitHub releases are the update source. Each release tag must match the version in `custom_components/freshairiq/manifest.json` (for example `v0.25.0.40` for manifest version `0.25.0.40`). Repository-owner and beta-tester instructions are documented in `HACS_BETA_SETUP.md`.

## Manual installation

1. Copy `custom_components/freshairiq` to `/config/custom_components/freshairiq`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and select **FreshAirIQ**.
4. FreshAirIQ can be added immediately without creating a room first. Outdoor air, rooms and advanced settings may be configured afterwards through **Devices & services → FreshAirIQ → Configure** or the FreshAirIQ dashboard gear.
5. Create or open the FreshAirIQ dashboard and add rooms/sensors at your own pace. Until the required climate sources exist, FreshAirIQ simply withholds ventilation calculations instead of inventing values.

The bundled FreshAirIQ card is registered automatically by the integration. No Browser Mod or `custom:button-card` is required for the integrated dashboard. Optional VOC/TVOC, PM2.5 and illuminance sensors are disabled/enabled globally through the same ConfigEntry settings in Devices & Services, the dashboard gear or the general FreshAirIQ card editor; per-card visibility can be controlled separately.

### Updating

Replace the complete `custom_components/freshairiq` directory with the new release and restart Home Assistant. Do **not** copy or create `__pycache__`; Python rebuilds it automatically. Learning data is stored separately in Home Assistant storage and survives a normal update/restart. The frontend URL contains the current FreshAirIQ release version as a cache key, so every release forces Home Assistant to load the matching dashboard JavaScript after restart.

### Reconfiguring the outdoor source

Open **Settings → Devices & services → FreshAirIQ → Reconfigure** to replace the fundamental outdoor-air source without deleting the integration or its learned data. FreshAirIQ accepts either one local `weather.*` entity or a matching outdoor temperature + humidity sensor pair. Broader comfort, house, notification and expert settings remain under **Configure**.

### Removing FreshAirIQ

1. Open **Settings → Devices & services → FreshAirIQ** and delete the integration entry.
2. Restart Home Assistant so the bundled frontend module is no longer loaded.
3. If you are uninstalling manually, remove `/config/custom_components/freshairiq` only after the integration entry has been deleted.
4. A stale Lovelace resource from a very old FreshAirIQ version can be removed from **Settings → Dashboards → Resources** if it remains after restart.

Removing the integration also stops FreshAirIQ calculations. Keep a diagnostic/export backup first if learned model history is important to you.

### Home Assistant action

FreshAirIQ registers `freshairiq.execute_intervention`. It executes only a measure FreshAirIQ has already marked as explicitly executable for the selected room. Merely configuring a fan, cover, purifier, dehumidifier or similar entity never enables autonomous actuation.

Example:

```yaml
action: freshairiq.execute_intervention
data:
  room_key: badezimmer
```

An optional `intervention_key` can select a specific executable recommendation. Climate/HVAC actions are deliberately not guessed when a safe mode/target cannot be derived unambiguously.

## Entity compatibility matrix

FreshAirIQ is device-brand agnostic. Compatibility is based on Home Assistant entity semantics rather than a manufacturer whitelist.

| Purpose | Supported Home Assistant entities | Requirement |
| --- | --- | --- |
| Outdoor reference | one `weather.*` entity **or** one numeric temperature `sensor.*` + one numeric relative-humidity `sensor.*` | Required |
| Room climate | numeric temperature `sensor.*` + numeric relative-humidity `sensor.*` | Required for calculation-enabled rooms |
| Ventilation opening | `binary_sensor.*` / contact entities that expose open/closed states | At least one required for calculation-enabled rooms |
| Alternative reference air | numeric temperature + humidity `sensor.*` pair | Optional |
| CO₂ | numeric `sensor.*` | Optional |
| VOC / PM2.5 / illuminance | numeric `sensor.*` | Optional |
| Pollen | numeric `sensor.*` | Optional |
| Shading | `cover.*` | Optional recommendation target |
| Mechanical ventilation / extraction / supply | suitable `fan.*`, `switch.*` or equivalent service-capable entity | Optional recommendation target |
| Dehumidifier / humidifier / purifier | suitable controllable entity | Optional recommendation target |
| Cooling / HVAC | `climate.*` | Optional recommendation context; FreshAirIQ does not invent unsafe HVAC modes or targets |
| Presence | `person.*`, `device_tracker.*`, plus optional presence/motion entities | Optional |

A configured optional actuator does **not** grant autonomous control. FreshAirIQ only exposes conservative executable interventions where an unambiguous Home Assistant service mapping exists; otherwise it remains recommendation-only. Calculation-enabled rooms with deleted required entities raise a native Home Assistant Repair issue. Temporarily `unavailable` entities do not create a Repair because they may recover without user intervention.

## Room setup

Each calculation-enabled room needs a temperature sensor, relative-humidity sensor, room volume and at least one ventilation contact. Volume can be entered directly in m³ or derived from length × width × height. A monitoring-only room may be displayed without participating in house totals, recommendations, learning or statistics and may therefore omit contacts.

Optional room inputs include an alternative source-air temperature/humidity pair (for example a conservatory), CO₂, user-defined floor/zone and multiple contacts. In Home Assistant 2026.8+ each FreshAirIQ room is exposed as a native configuration subentry: open that room in the FreshAirIQ integration to replace its sensors, assign per-contact compass directions or adjust contact delays.

## House, occupants and night model

The house profile contains property type, number of adults and children, optional Home Assistant `person`/`device_tracker` assignments for adults and children, the behaviour of residents without trackers, night start/end as time pickers and the night-forecast switch. It is valid to configure children without phones; no fake tracker is required.

FreshAirIQ separates configured household size from current expected occupancy. Presence changes are listened to directly and recalculate forecasts immediately. The short-term prior therefore drops when tracked residents leave and rises again when they return or when guests are entered. The long-term adaptive ventilation threshold still uses the configured household baseline so leaving home does not paradoxically lower the house threshold.

FreshAirIQ uses conservative internal biological priors for occupant and background moisture. Observed overnight behaviour is stored persistently, normalised to the configured household, and then scaled back to the currently expected occupancy. This prevents a night with only one person home from permanently teaching the model an unrealistically low four-person night rate.

## Heating and energy costs

Select the actual heating system. FreshAirIQ then asks only for relevant inputs:

- heat pump: electricity price and COP;
- gas: gas price per kWh and efficiency;
- heating oil: price per litre, kWh per litre and efficiency;
- district heating: price per kWh and efficiency;
- direct electric: electricity price.

The five-minute continuation forecast and room details include the estimated reheating cost only when the forecast indicates a temperature loss. The calculation models sensible heat in the exchanged air; it does not claim to model the full building thermal mass.

## Learning

FreshAirIQ learns a per-room effective air-exchange rate from valid completed ventilation sessions. Learned values and sample counts survive restarts. The details popup shows the current learned rate, sample count and diagnosis. The learner does **not** rewrite user-selected thresholds or profile settings. Learning data can be reset manually from the integration options.

## Pollen and wind

A pollen sensor can be selected as the outdoor pollen source. When pollen protection is enabled and the configured index limit is exceeded, normal ventilation is vetoed. Window orientation can optionally modify the learned airflow estimate using weather wind bearing/speed; the correction is deliberately bounded so it cannot dominate measured learning data.

## Configuration menu

**Configure → FreshAirIQ** contains the global settings: outdoor source; room administration (add/remove/order); freely defined floors/zones; operating profile; house & occupants; pollen & wind; heating & energy costs; notifications; statistics & history; model parameters; learning reset; and save/reload. Room-specific configuration is intentionally kept on the native room subentries instead of being duplicated in the global menu. Model parameters are expert controls; the adaptive threshold is recommended unless a fixed strategy is intentionally required.

## Main dashboard semantics

- **− ml, green:** water removed / removable.
- **+ ml, red:** water added / expected moisture gain.
- **Next 5 min:** expected moisture change, temperature change and estimated reheating cost.
- **Night:** expected added moisture until the configured night end.

Press **FreshAirIQ Details** for house state, threshold, pollen/wind context, profile, learned values, statistics and floor-grouped room details.

## Known limitations

- Surface humidity is estimated from room conditions; it is not a wall-surface measurement.
- Moisture, temperature and cost projections are forecasts and therefore include model uncertainty.
- Heating-cost estimates cover exchanged-air sensible heat and do not claim to model the complete thermal mass of the building.
- Pollen, PM2.5 and VOC decisions are only as reliable as the configured source sensors.
- Wind/orientation is a bounded airflow modifier, not a CFD simulation.
- Optional actuators are recommendation targets by default; FreshAirIQ never assumes that every `fan`, `switch` or `climate` entity is safe to actuate automatically.
- Very unusual floor plans, mechanically balanced ventilation systems or rooms without representative sensors may require manual validation of recommendations.

## Troubleshooting

**FreshAirIQ does not appear after installation:** verify that `custom_components/freshairiq/manifest.json` exists, restart Home Assistant completely and check **Settings → System → Logs** for a manifest/import error.

**The dashboard card reports a configuration error:** first reload the browser/app frontend after the Home Assistant restart. FreshAirIQ registers its bundled card automatically; no manual Browser Mod or button-card resource is required. Remove only stale FreshAirIQ loader/resource entries left by very old releases.

**A room no longer produces recommendations:** verify its required temperature, humidity and ventilation-contact entities are available and that **Include in calculations** is enabled. Optional sensors/actuators may be unavailable without breaking the core room calculation.

**Outdoor reference is wrong or was renamed:** use **Reconfigure** for the global outdoor source. Use the room editor for room-wide reference air and the per-opening reference settings when different windows/doors lead to different air zones.

**Values look implausible after replacing sensors or changing the building:** inspect the room details and learning status before resetting learning. A sensor with a changed offset can legitimately invalidate old learned behaviour. Export diagnostics before resetting if the issue needs investigation.

Real-home validation remains important after installation, sensor replacement or major configuration changes.

## Branding

- **Project:** FreshAirIQ
- **Developer:** rupascha
- **Tagline:** *Intelligent lüften. Gesund wohnen. Energie sparen.*
- **Integration domain:** `freshairiq`

### HACS icon note (Home Assistant 2026.3+)
FreshAirIQ ships the complete local Home Assistant brand set in `custom_components/freshairiq/brand/`. Home Assistant 2026.3+ can use these files directly. If HACS itself still shows **“icon not available”** in its Downloads list, this is a known upstream HACS frontend limitation: affected HACS builds still request custom-integration icons from the legacy public brands CDN instead of Home Assistant's authenticated local brands API. The FreshAirIQ release gate verifies that all local brand assets are present so a release cannot accidentally regress its branding.
