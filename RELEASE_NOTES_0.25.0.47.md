# FreshAirIQ 0.25.0.47 – Release Asset & Changelog Hygiene Hotfix

This mini hotfix changes release/documentation hygiene only. Ventilation physics, recommendations, forecasts, learning, diagnostics payload semantics and Decision Intelligence are unchanged.

## Changes

- The tag release job downloads the exact CLEAN ZIP built by the mandatory quality workflow.
- The downloaded ZIP is revalidated with `tools/github_release_gate.py --zip` immediately before publishing.
- The verified archive is renamed to a versioned CLEAN release asset and attached directly to the GitHub release.
- The duplicate/mislabelled 0.25.0.45 changelog entry is corrected to its actual historical version 0.25.0.44.
- Redundant secondary `# Changelog` wrapper headings are removed without deleting historical release content.

## Scope

No intentional functional changes were made to Home Assistant runtime behavior, room calculations, ventilation decisions, thresholds, session handling, UI logic, forecasts, learning weights or Decision Intelligence.
