# FreshAirIQ 0.25.1.13

## Freshy night-window alignment

- Freshy now follows the configured FreshAirIQ night window (`night_start_hour` / `night_end_hour`).
- Bedtime starts exactly 60 minutes before the configured night start.
- During the configured night window Freshy sleeps; active ventilation still takes priority and keeps the sailing animation.
- Adds browser-level behavior coverage for custom night times, midnight crossover, defaults and live-state priority.
- No ventilation physics, learning, sensor-recovery or dashboard-navigation behavior changed.
