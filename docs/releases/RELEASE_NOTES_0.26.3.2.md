# FreshAirIQ 0.26.3.2

## Important fix
0.26.3.1 contained a refactoring mistake: in rare cases (when the recommendation had no status of its own) the update cycle could fail and FreshAirIQ would stop updating. This is fixed, and a new automatic check now verifies on every path that no value is read before it is set. **If you installed 0.26.3.1, please update.**

## Better tested decisions
The house-wide decision rules (when to air, when a floor is aired together, when to close because of cooling, what to do tonight) are now a separate module with 114 tests that check each limit exactly at its edge.
