# FreshAirIQ 0.24.9.0

## Repair-aware Home Assistant runtime

FreshAirIQ now creates a native Home Assistant Repair issue when an entity that is mandatory for the configured calculation has actually been removed from Home Assistant. Temporary `unknown`/`unavailable` states do not create a Repair: the integration checks both the live state machine and the entity registry before deciding that user intervention is required.

Covered mandatory references are the global outdoor source and, for every calculation-enabled room, temperature, humidity and configured ventilation contacts. Monitoring-only rooms are intentionally excluded. The Repair is cleared automatically after the configuration/entity reference is restored and is also cleaned up on a successful integration unload.

Repair synchronization is deliberately non-critical: a failure in Home Assistant's Repairs UI cannot break FreshAirIQ's coordinator update or prevent an otherwise successful setup/unload.

## Entity-platform quality audit

The three FreshAirIQ number controls now use native entity translation keys instead of hard-coded German entity names. English and German translations are supplied for forecast horizon, adult overnight guests and child overnight guests.

Configuration controls (`number`, operating-profile `select`, reset `button` entities) now use Home Assistant's `EntityCategory.CONFIG`. The compatibility documentation now contains an explicit Home Assistant entity matrix for required sensors, optional IAQ sensors, contacts, presence entities and optional actuator targets.

## Validation

- Existing local regression suite: 503/503 passed.
- Pure-logic coverage: 95.07%, maintaining the hard >=95% CI gate.
- Additional real-Home-Assistant CI tests cover Repair detection/clearance, false-positive prevention and configuration entity metadata.
- The real Home Assistant tests are CI-only in the current offline build environment and are not claimed as locally executed.
