# FreshAirIQ 0.25.2.10

## Guided Setup & Settings Architecture Hotfix

- Replaces the technical first-run mode dropdown with two explicit paths: Quick setup and Precise setup.
- Quick setup now establishes a usable outdoor-air reference before room setup.
- Quick rooms require temperature and humidity sensors and no longer inject a fake 15 m² default.
- The provisional 2.40 m room height remains transparent and can be corrected later.
- The success screen exposes two explicit actions: add another room or start FreshAirIQ.
- Precise setup stays precise for every additional room and uses the existing mobile-first sectioned room form.
- Native Home Assistant options and dashboard settings use non-overlapping canonical categories.
- Support/diagnostics remain separate from Settings.
- Existing configuration, physics, learning and diagnostic contracts are preserved.
