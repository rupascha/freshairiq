# FreshAirIQ 0.26.2.4

Hotfix completing the platform/UI and mechanical-ventilation work.

- Cross-platform detail/support surfaces hardened against host theme contrast differences.
- Diagnostics support send uses an embedded FreshAirIQ form and explicitly identifies the remote support destination.
- Room humidity/temperature history includes readable Y-axis values.
- Room icons are configurable in quick and central room configuration with DE/EN descriptions.
- Relevant sensor selectors are constrained by Home Assistant device classes where a device class exists.
- Mechanical ventilation accepts legacy single entities and multiple fan/switch entities or stage entities. Any active configured entity starts/maintains the mechanical ventilation session. Multiple stages are never auto-selected or switched by assumption.
