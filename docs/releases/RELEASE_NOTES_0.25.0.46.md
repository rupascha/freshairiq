# FreshAirIQ 0.25.0.46 – Android Touch & Settings Contract Hardening Hotfix

This hotfix leaves ventilation physics, recommendation logic, forecasts, learning and Decision Intelligence unchanged.

## Changes

- Added a dedicated Android Home Assistant WebView regression that uses trusted Chromium touch events (`Input.dispatchTouchEvent`) to perform a real finger-style swipe inside a long detail overlay. The test verifies that the overlay actually scrolls and that its position survives a rerender.
- Kept the cross-browser wheel-scroll regression as a separate desktop/browser check.
- Turned the native settings key contract into an executable runtime guard: every native Config Flow option field now resolves through `native_option_key(...)`, which rejects keys not present in the canonical `NATIVE_OPTION_KEYS` set.
- Added semantic regression coverage proving that all 92 native option keys are bound to the canonical contract and that no extra option key bypasses it.
- Aligned manifest, frontend, quality policy, package metadata and release artifact naming on v0.25.0.46.
- Clean release directory/ZIP naming now matches the actual hotfix name.

## Scope

No intentional changes were made to moisture calculations, ventilation decisions, thresholds, session handling, forecasts, learning weights, diagnostics protocol payloads or Decision Intelligence.
