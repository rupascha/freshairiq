# FreshAirIQ 0.6.0 — 26 requested changes

This release is built from the 0.5.0 integrated-dashboard codebase and ports the relevant calculation behaviour from the supplied V14.2.1 YAML while implementing all 26 requested product changes.

| # | Requested change | 0.6.0 implementation |
|---:|---|---|
| 1 | Remove “CLIMATE INTELLIGENCE · V14.2.1” | Removed from the bundled main card. |
| 2 | Moisture gain red | UI maps physical gain to red `+ ml`. |
| 3 | 5-min temperature + reheating cost | Main card and room popup show expected ΔT and estimated reheating cost. |
| 4 | Details popup | `FreshAirIQ Details` opens the bundled modal; Browser Mod is not required. |
| 5 | Sort rooms | Configure → Rooms → Sort rooms, with persistent `sort_order`. |
| 6 | Assign floors | Each room has a floor; popup groups rooms by floor. |
| 7 | Removed moisture green/minus; entered red/plus | Centralized sign/colour helper in the frontend. |
| 8 | Default threshold = 10% of house water | New default dynamic threshold; fixed mL remains a compatibility option. |
| 9 | Property type | House/apartment/maisonette/other added to House & occupants. |
| 10 | Use current YAML calculation logic | Absolute-humidity, adaptive decisions, learned rates, cross-ventilation, 5-min logic and exponential full-session replacement retained/aligned. |
| 11 | Night forecast on main tile | Added as a fifth live main metric. |
| 12 | Main tile live | Coordinator refreshes immediately on source/contact changes; timed refresh remains a fallback. |
| 13 | Simplify m³ vs dimensions | No volume-mode selector. Enter direct m³ or all dimensions; complete dimensions take precedence. |
| 14 | Heating cost not heat-pump-only | Heat pump, gas, oil, district heating and electric each have appropriate fields. |
| 15 | Better explanations and units | Configuration translations/descriptions and selector units expanded. |
| 16 | Visible room excluded from calculations | `include_in_calculations=false` gives a monitor-only room; still visible in popup. |
| 17 | Show what IQ learned | Popup exposes learned exchange rate, samples, learning status and last diagnosis. User settings are not silently rewritten. |
| 18 | Adults/children should feed IQ; no manual moisture sliders | Adults/children use internal priors and adaptive night learning; manual person/day moisture fields removed from UI. |
| 19 | Reconsider 45-min learning maximum | Configurable `learning_max_duration_min`, default 120 min. |
| 20 | Statistics up to 30 days | Selectable 1–30 days; storage retention supports 30 days. |
| 21 | Profile-specific settings | Profile selection now leads to profile-relevant detail settings. |
| 22 | Explain profiles | German/English profile descriptions explain what each changes. |
| 23 | Better people/night UI | Adult/child sliders and native time selectors for night start/end. |
| 24 | Optional window orientation + local weather | Orientation per room plus bounded weather wind-bearing/speed airflow correction. |
| 25 | Pollen in every ventilation decision | Optional global pollen source/threshold; each room decision receives current pollen index. |
| 26 | Individual contact opening delay | Persistent delay map per room/contact with dedicated configuration step. |

## Validation performed

- Python bytecode compilation for the integration.
- JavaScript syntax check for the bundled card.
- German and English translation JSON validation.
- Pure calculation checks for absolute humidity, pollen veto, >45-minute learning, heating systems and night forecast.

A full Home Assistant pytest run requires the Home Assistant Python package/runtime and therefore was not available in the build container. Install first on a test Home Assistant instance and compare several real sessions before replacing a known-good production configuration.
