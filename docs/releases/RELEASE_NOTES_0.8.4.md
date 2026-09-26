# FreshAirIQ 0.8.4 — Recommendation Engine v2

FreshAirIQ no longer uses the main dashboard as a list of competing room actions. Version 0.8.4 introduces a house-level recommendation engine that converts room diagnostics into one prioritised action.

## What changed

- Added a pure **Recommendation Engine v2** with a single house action: ventilate, cross-ventilate, continue, close, wait, pollen postponement, sensor check or no action.
- Room problems can still trigger **targeted ventilation below the house threshold** when RH, mould/surface risk or CO₂ makes it justified.
- High room humidity with unsuitable outdoor/reference air now produces **wait / do not ventilate** with a physical explanation instead of a contradictory ventilation call.
- Recommendation utility combines room severity, removable moisture, absolute-humidity difference, wind/orientation airflow, learned room behaviour, temperature loss and estimated reheating cost.
- Configured cross-ventilation pairs are preferred when both openings are useful and the pair improves the action.
- Added persistent RH context: time above the ventilation-start RH and a five-minute-sampled RH trend. This prevents a short sensor spike from being treated like a sustained problem.
- Corrected profile-specific delta wording so the dashboard no longer says that a room needs 2.5 g/m³ when the Dehumidify profile has already reduced the effective requirement.
- House notifications now use the same single intelligent recommendation instead of sending a grouped dump of room actions.

## Dashboard

The old multi-row recommendation list on the main card has been replaced by one larger **INTELLIGENTE EMPFEHLUNG · ENGINE V2** panel. It shows, in this order:

1. what to do,
2. where to do it,
3. approximate duration,
4. why this action was selected,
5. expected moisture effect,
6. what happens next.

Detailed per-room states and reasons remain available under **Räume** and in each room's detail view.
