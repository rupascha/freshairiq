# FreshAirIQ 0.9.7.0 — Future Intelligence & Outcome Feedback

- Decision Engine v2 consumes hourly forecasts from the configured Home Assistant weather entity when temperature and humidity are available.
- 15/30/60-minute options use interpolated future outdoor temperature, relative humidity and absolute humidity.
- Missing forecast data never blocks FreshAirIQ; affected horizons retain the conservative v0.9.6 current-condition model.
- Recommendation-linked ventilation sessions now retain their predicted moisture removal, temperature change and cost.
- After completion, FreshAirIQ compares prediction with reality and learns bounded per-room moisture and temperature calibration factors.
- Learned outcome calibration is gradually blended into future simulations only after real samples accumulate.
- IQ activity can expose weather simulation and learned prediction feedback without enlarging the main dashboard permanently.

No existing room physics, session handling, notification logic or configuration schema was removed.
