# FreshAirIQ 0.9.4.7 — moisture-potential hotfix

- Restores the practical moisture forecast to the physical basis `AH inside - AH outside/reference`.
- The visible "removable" value is no longer the theoretical 100% room-air replacement. It is scaled by the learned per-room air-exchange rate for the recommended ventilation duration.
- The sign is preserved: dry outside/reference air produces removable moisture; wetter outside/reference air produces a possible moisture gain and an explicit "Jetzt nicht lüften" recommendation.
- Room breakdown and Recommendation Engine use the same realistic learned potential.
- Theoretical full-replacement potential remains available internally for diagnostics.
- Live ventilation moisture balance is unchanged.
