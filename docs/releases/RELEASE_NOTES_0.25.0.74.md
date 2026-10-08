# FreshAirIQ v0.25.0.75 — English Dashboard UI Hotfix

## Changes
- Adds automatic dashboard language selection from the Home Assistant user locale.
- German Home Assistant profiles keep the existing German FreshAirIQ UI unchanged.
- English and other non-German profiles receive an English FreshAirIQ dashboard UI.
- Covers the main card, details, rooms, recommendations, learning, settings and dynamic status/reason texts.
- Existing Home Assistant config/options translations remain unchanged and complete.
- No ventilation calculations, learning logic, diagnostics transport or scroll/navigation behavior changed.

## Compatibility
- German remains the existing UI for `de` locales.
- English is the fallback dashboard language for all other locales until additional translations are added.
