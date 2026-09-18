# FreshAirIQ v0.14.0.0 – Seasonal & Long-Term Learning

Phase 10 adds seasonal and ageing-aware learning.

- Each room learns separate winter, spring, summer and autumn moisture-source profiles.
- A slow long-term baseline is learned independently from seasonal behaviour.
- Seasonal influence is blended against the long-term baseline and remains bounded.
- Sparse seasonal data stay close to neutral instead of overfitting.
- Stale observations lose influence with an exponential 120-day half-life at evaluation time.
- Seasonal factors refine routine projections used by anticipation, day/night planning and night forecasts.
- Room payload exposes season, seasonal factor/maturity, seasonal source rate and long-term source rate.
- Intelligence Engine reports seasonal maturity and can show “Saisonverhalten berücksichtigt”.
- Existing health, pollen, live-coach and real-time physical rules remain authoritative.
