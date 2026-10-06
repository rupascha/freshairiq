# FreshAirIQ 0.25.3.5

## Multi-goal ventilation and mechanical exhaust

- CO₂ is a regular room ventilation goal and is configured with the primary room sensors.
- Exhaust fans are configured with the normal room inputs. ON starts a mechanical ventilation session; OFF ends it.
- Mechanical exhaust has isolated learning (`mechanical_exhaust`); combined window + exhaust sessions are kept out of pure opening models.
- Rooms can prioritise dehumidification, CO₂/air quality and temperature comfort. Safety limits remain authoritative.
- Thermostat comfort targets are snapshotted before ventilation; frost-protection/off changes cannot corrupt an active session. A manual/fallback target supports summer operation.
- Dashboard room views show compact goal status and per-goal ETA when evidence is available.
- Laundry drying is now implemented through the backend moisture-source contract.
