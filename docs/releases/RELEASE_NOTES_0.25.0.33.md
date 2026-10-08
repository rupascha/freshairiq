# FreshAirIQ 0.25.0.33 – Maximum Hardening Hotfix

This hotfix hardens measurement-evidence consistency and Android compatibility without changing the proven ventilation physics.

## Changes

- The live dashboard only says **LERNT JETZT** after both room temperature and humidity have supplied valid in-session timestamp evidence. Until then it explicitly reports **LÜFTUNG WIRD BEOBACHTET**.
- A session that fails the strict timestamp gate can no longer seed humidity/reference baselines used by later repeat-recommendation logic. The fact that a ventilation occurred is still retained for temporal cooldowns.
- Android is now a first-class CI target via an Android 15 / Home Assistant WebView-like Chromium project with touch, mobile rendering, device-pixel ratio and four viewport sizes.
- Regression tests verify the backend baseline gate and the frontend learning-state wording semantically.
- Staging/Diagnostics copy is version-neutral so future releases do not inherit stale milestone labels. Diagnostics HA and Diagnostics Hub transport contracts are intentionally unchanged.

## Unchanged

Ventilation physics, absolute-humidity calculations, forecast formulas, thresholds, session timestamp-learning rules, diagnostics schema, upload schema, Hub endpoints and migration compatibility remain unchanged.
