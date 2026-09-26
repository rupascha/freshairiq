# FreshAirIQ 0.23.0.11 – Hotfix

Focused correctness hotfix for per-opening reference-air recommendations.

- Mixed open air sources no longer force a blanket room-close presentation when a useful opening can remain open and the harmful opening can be closed selectively.
- Configured local reference sensors fail closed when unavailable or incomplete; they can no longer silently fall back to outside air.
- Opening ranking no longer applies wind/orientation twice. The physical 5-minute effect already contains the airflow factor.
- Added regression coverage for mixed outside/winter-garden openings, unavailable local references and non-duplicated airflow ranking.
- No changes to learning parameters, canonical room physics, stored learning data or the underlying `evaluate_room` calculation.
