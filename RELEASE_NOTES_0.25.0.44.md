# FreshAirIQ 0.25.0.44 — Native Config, Scroll & Quality Hotfix

- Monitor-only / calculation-disabled rooms remain visible in diagnostics but are no longer counted as room sensor-quality errors. Genuine data-quality failures in calculation-active rooms remain unchanged.
- Fixes nested detail-window touch scrolling in Web/Home Assistant WebView by removing the ancestor `touch-action: none` blocker and using an explicit native vertical scroll container. Scroll-position preservation remains active.
- Restores a fully documented German Devices & Services setup/options flow with native Home Assistant selectors, descriptions, documented defaults and examples. The setup/options flow stays German even when the Home Assistant frontend user is set to English; runtime entity/device translations remain locale-specific.
- Dashboard gear and Devices & Services now share one canonical native option-key contract and continue to write the same ConfigEntry. Existing room/level operations and live reload behaviour are preserved.
- Configuration UX follows the robust native Home Assistant pattern also used by Better Thermostat: guided sections, native selectors, translated field descriptions, defaults/examples and separate advanced pages.
- No change to ventilation physics, recommendation prioritisation, forecast formulas, learning coefficients, Decision Intelligence, sensor entity IDs or stored room configuration.
