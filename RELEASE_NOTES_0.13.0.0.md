# FreshAirIQ v0.13.0.0 – Self-Learning Day & Night Planning

Phase 9 adds multi-hour planning.

- Plans up to eight hours ahead using configured Home Assistant hourly weather data.
- Combines future outdoor absolute humidity/temperature, learned room moisture routines, current removable moisture, health pressure and the existing overnight model.
- Compares "now", future hourly ventilation windows and "after the night".
- Future windows need a clear score margin before they replace the current plan (anti-flapping hysteresis).
- Real-time close/continue/sensor and pollen protection remain authoritative.
- Existing Decision Engine still governs immediate ventilation; the planner mainly refines wait/prepare/okay states.
- Exposes a compact day_night_plan object for future UI details without enlarging the main dashboard.
