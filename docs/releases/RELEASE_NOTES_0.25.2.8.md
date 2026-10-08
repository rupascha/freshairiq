# FreshAirIQ 0.25.2.8 — Bounded Three-State Uncertainty Hotfix

This hotfix bounds temporary three-state `unknown`/`unavailable` holding to 30 seconds. Longer gaps become stale/uncertain and quarantine specialist opening learning without fabricating a closed state. Physical session start timestamps now use the same debounced state/timestamp truth as the session lifecycle.
