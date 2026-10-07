# FreshAirIQ 0.26.2.6

- Restores immediate tile-style room and ventilation-goal ordering in dashboard settings and keeps native priority sorting on the sorting step after a confirmed move.
- Adds previous-page navigation to multi-step room editing and compact humidity / temperature / CO₂ ventilation-impact projections.
- Refines recommendation scope so blocked idle goals do not create misleading room-specific negative recommendations.
- Adds deterministic, learning-aware recommendation wording without changing canonical decisions.
- Strengthens protection arbitration for critical CO₂ and surface-moisture/mould risk, including active ventilation and authoritative close/session-end signals.
- Coordinates simultaneous critical rooms so actionable rooms are no longer hidden behind the single worst room.
- Adds independent per-card dashboard text sizing for recommendation, goals, rooms, metrics, details and supporting text in fixed 80–150% steps. Existing cards remain at 100%, preserving established desktop/mobile typography.
- Completes goal-area typography coverage so all visible goal text follows the selected size without affecting other dashboard areas.
