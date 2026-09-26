# FreshAirIQ 0.9.5.0 — Intelligence Layer Phase 1

- Adds a central `iq_state` intelligence layer without replacing the existing room, forecast or recommendation physics.
- IQ state now exposes current mode, activity, decision, explanation, combined confidence, data quality and learning maturity.
- Combined IQ confidence incorporates forecast confidence, sensor/data quality, room learning maturity, presence confidence and night-model maturity.
- Adds persistent behavioural learning per room: recommendation opportunities, followed/missed recommendations, follow rate, follow delay, preferred real ventilation duration and deviation from recommended duration.
- A ventilation session can now be linked to the active FreshAirIQ recommendation so future models can distinguish recommended behaviour from independent/manual ventilation.
- Completed sessions continuously update the resident-duration model while preserving the established physical air-exchange learning model.
- Existing dashboard layout is intentionally retained in this phase. The new IQ state is exposed first so the adaptive dashboard can be built on stable backend data in the next phase.
- Version metadata aligned to 0.9.5.0.
