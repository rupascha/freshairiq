# FreshAirIQ 0.25.4

## Multi-goal house/floor consistency
- House and floor low-moisture-return is now a soft efficiency signal: it no longer ends ventilation while CO₂ or temperature remains open and achievable.
- Hard protection and thermal protection remain dominant.
- Aggregate Decision Brain data now carries the canonical presentation scope, floor and participating room names for both Classic and Freshy.

## Dashboard
- Hierarchical scope and goal text uses readable sizes instead of 7–9 px compression.
- Freshy sustained ventilation uses a smaller, calmer leaf-wing geometry while active ventilation remains more dynamic.
- Existing progressive disclosure remains the mechanism for keeping the card compact.

## Compatibility
- Internal persistence/diagnostic schema versions are unchanged; this is a release-version bump only.
