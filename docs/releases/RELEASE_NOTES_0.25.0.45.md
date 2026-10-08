# FreshAirIQ 0.25.0.45 – Release, Scroll & Locale Hardening Hotfix

This hotfix keeps the ventilation, forecast, learning and Decision Intelligence logic unchanged and hardens release safety and configuration UX.

## Changes

- GitHub releases now wait for the complete reusable Continuous Quality workflow instead of a reduced duplicate validation job.
- Added a real Playwright scroll regression that opens a long detail overlay, performs actual scrolling and verifies the position survives a rerender.
- Restored locale-correct native Home Assistant configuration: English source/fallback strings and a separate complete German translation.
- Corrected the “add another room” default label to match the actual default (`on`).
- Corrected the statistics menu description from 1–30 to the real 1–365 day range.
- Strengthened the native-vs-dashboard settings contract regression checks across all canonical option keys.
- Stability runtime is now reported as an advisory metric; deterministic behaviour and memory limits remain hard failures, while runtime performance continues to be enforced by the dedicated performance regression gate.
- The v0.25.0.44 monitor-only/Wintergarten diagnostic correction remains unchanged.

## Scope

No intentional changes were made to ventilation decisions, moisture calculations, forecasts, learning weights, session handling or Decision Intelligence.
