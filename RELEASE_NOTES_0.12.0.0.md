# FreshAirIQ v0.12.0.0 – Predictive Moisture & Behaviour Anticipation

Phase 8 adds cautious pre-event intelligence.

- Looks ahead across learned room moisture routines instead of evaluating only the current hour bucket.
- Projects 15/30/60/120-minute internal moisture generation.
- Detects learned threshold crossings and meaningful future moisture-source spikes.
- Requires routine maturity and confidence before an event can influence the recommendation.
- Can recommend short pre-ventilation when a learned near-term event is likely and useful removable moisture already exists.
- Otherwise exposes the event only as an IQ observation; it does not invent an action.
- Future waiting options receive a stronger penalty when a mature learned moisture event would make waiting worse.
- Running ventilation, close, sensor-error, direct ventilation and pollen-veto states remain authoritative.
- No new large dashboard card was added.
