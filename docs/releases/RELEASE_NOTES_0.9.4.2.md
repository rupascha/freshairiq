# FreshAirIQ 0.9.4.2 – Room detail scroll hotfix

This hotfix is based strictly on 0.9.4.1.

## Fixed

- The room detail window now keeps its own scroll position if the FreshAirIQ card has to re-render.
- Browser scroll anchoring is disabled for the room detail scroll container, preventing sporadic jumps to the top in iOS/Home Assistant WebView.

No calculation logic, recommendation logic, room payloads, settings, or visual layout were changed.
