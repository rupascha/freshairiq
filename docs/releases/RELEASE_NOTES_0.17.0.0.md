# FreshAirIQ v0.17.0.0 – Unified Decision Brain

This release converts the existing intelligence architecture into one visible,
user-facing decision.

## Unified Decision Brain
- Reconciles current physical recommendation, short-term simulation, multi-hour
  planning, learned room/routine behaviour and house-strategy feedback.
- Produces one decision label, headline, action, explanation, quantified impact,
  comparison with the relevant alternative and selected rooms.
- Does not weaken the v0.16 safety/consolidation invariants.

## New visible recommendation
The main dashboard recommendation is rebuilt around the actual decision:
- what to do now,
- where,
- how long,
- expected moisture effect,
- expected temperature effect,
- estimated reheating cost,
- confidence,
- why this action is preferred,
- and, when relevant, a direct "now vs later" comparison.

## Fix
- Fixes the old active-ventilation dashboard reference to an undefined `rec`
  variable.

Room cards, room-detail navigation and the established iOS scroll/touch fixes are
left unchanged.
