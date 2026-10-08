# FreshAirIQ v0.16.0.0 – Intelligence Consolidation / Release Candidate

Phase 12 consolidates the complete FreshAirIQ intelligence stack.

## Stability
- Final invariant gate after Recommendation, Anticipation, Decision, Live Coach, Day/Night Planner and House Strategy.
- Active real ventilation cannot be overridden by a later future plan.
- Close recommendations from actual running sessions are authoritative.
- Stale room references are removed before Home Assistant state output.
- NaN/infinite numeric values are blocked and key outputs are bounded.
- Final ventilation duration always respects configured min/max limits.

## Persistence / migration
- Learning-store normalisation now repairs malformed persisted dictionaries.
- Manual learning reset clears seasonal/routine/strategy room learning through room defaults plus the global house-strategy model.
- Stale active advice is also removed during a manual learning reset.
- Running sessions remain preserved by the existing reset protection.

## Scope
No new major AI feature was added. v0.16.0.0 is the first consolidation/release-candidate build of the complete intelligence architecture.
