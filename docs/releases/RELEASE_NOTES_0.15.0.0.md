# FreshAirIQ v0.15.0.0 – House-Wide Strategy Learning

Phase 11 adds a house-level learning layer.

- Learns ventilation outcomes across single-room, same-floor and multi-floor strategies.
- Separates normal ventilation from cross-ventilation outcomes.
- Separates away, normal occupancy and high-occupancy situations.
- Learns success rate, moisture removal per minute and cost per 100 ml removed.
- Uses Bayesian neutral priors so sparse samples cannot dominate decisions.
- Exposes a bounded efficiency factor and maturity for the current house strategy.
- Adds compact explanation when a mature strategy is historically above/below average.
- Keeps all health, mould, CO₂, pollen and real-time physical rules authoritative.
- Does not hardcode any room names, floors or sensors.
