# FreshAirIQ 0.25.1.3 – Repository Documentation Cleanup Hotfix

## Repository structure
- Moved historical and current release notes from the repository root to `docs/releases/`.
- Updated release tooling, release gates and regression contracts to use the new release-note location.
- Future version bumps now create release notes directly in `docs/releases/`.

## English documentation
- Added a complete English README as `README_EN.md`.
- Added an explicit German/English language switch at the top of both README files.
- The German README remains the default project landing page and is otherwise unchanged.

## Scope
- Documentation/repository-maintenance hotfix only.
- No changes to ventilation calculations, learning, diagnostics, room logic, dashboard behavior, or mascot animations.
