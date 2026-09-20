# FreshAirIQ 0.25.0.40 — Learning & UI Stability Hotfix

- Migrates only provable persisted calendar evidence into the independent-day learning gates; no days are inferred from counters.
- Makes partial seasonal learning visible while preserving strict full-season/full-year optimization requirements.
- Qualifies forecast-validation accuracy by sample depth.
- Improves diagnostics transport observability (registration, initial snapshot, regular upload).
- Attaches an allow-listed anonymous client context to explicit user feedback.
- Fixes Android/WebView nested detail scrolling by removing gesture-cancelling touch handlers and using native scrolling with overscroll containment.
- Preserves the surrounding Home Assistant scroll position when FreshAirIQ dialogs are opened and closed.
- No changes to absolute-humidity physics, ventilation potential, recommendation prioritization, or core decision formulas.
