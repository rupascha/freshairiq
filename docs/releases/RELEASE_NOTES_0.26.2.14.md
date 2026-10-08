# FreshAirIQ 0.26.2.14

Hotfix: Rooms overview, room saving and dashboard UI.

## Fixed
- **Rooms button / tile did nothing.** Root cause was a render-time `TypeError` (`this._lang is not a function`) when any room had an active ventilation goal – not the click wiring.
- **Saving a room in the dashboard settings failed** because of an undefined variable.
- **Goal pills were unstyled on the card**, making room tiles unnecessarily tall.

## Hardened
- Render error boundary with a readable error code (`FAIQ-UI-RENDER-001`, `FAIQ-UI-ROOM-001`) and a retry button instead of a silent failure.

## Improved UI
- Larger touch targets (58 px quick-action tiles), icons, status chips, rooms summary strip, 2-column room grid on wide screens, larger small texts, tap feedback and keyboard focus.

## Upgrade note
The frontend URL contains the version (`?v=0.26.2.14`), so browsers and the Companion app load the new file automatically after the update and a Home Assistant restart.
