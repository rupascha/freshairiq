# FreshAirIQ 0.23.0.8 – Dashboard Card Loader Rollback Hotfix

- Restores the proven direct frontend registration architecture used by FreshAirIQ 0.21.x through 0.23.0.0.
- `freshairiq-card.js` is again the module loaded by Home Assistant and the Lovelace resource; `freshairiq-loader.js` is no longer in the active card loading path.
- Removes the safe-panel dependency from the active integration setup.
- Restores the generated dashboard to the full `custom:freshairiq-card` instead of a launcher tile.
- Keeps all current 0.23.0.7 FreshAirIQ UI, settings, learning, recommendation and forecast logic.
