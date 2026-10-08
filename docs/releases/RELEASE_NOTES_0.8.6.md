# FreshAirIQ v0.8.6 – Presence-aware Intelligence

Version 0.8.6 makes both the configurable live forecast and the overnight forecast occupancy-aware.

## Presence mapping

The household settings now accept optional Home Assistant `person.*` or `device_tracker.*` entities for adults and children. Residents with a known `home` state count toward the moisture-production prior; residents known to be away do not. Unknown or unavailable states are treated probabilistically and reduce presence confidence.

Residents without phones remain first-class occupants. With **Bewohner ohne Handy folgen dem Haushalts-Anwesenheitssignal** enabled, untracked residents follow the reliable household signal: when all known trackers are away they are treated as away too; when somebody is home they continue to count. This specifically supports children without their own phone.

## Guest mode

FreshAirIQ adds two persistent number entities:

- `Übernachtungsgäste Erwachsene`
- `Übernachtungsgäste Kinder`

The integrated card exposes a **Gäste** button with direct +/- controls. Every change immediately refreshes the short-term and night forecasts. `0 Erwachsene / 0 Kinder` effectively disables guest mode.

## Intelligent overnight forecast

The overnight model now combines:

- current expected adults and children, including guests;
- conservative biological/background priors;
- household-normalised persistent night learning;
- the current learned room moisture-source residual for the near-term part of the night;
- absolute outdoor humidity;
- windows that are actually open;
- learned room air-exchange rates;
- wind/orientation and cross-ventilation;
- remaining time until the relevant night end.

A dedicated overnight confidence score reflects night-learning samples and presence certainty. Weather and trend contributions are exposed as status attributes and explained in the dashboard.

## Compatibility

Existing installations do not need to assign trackers. Without presence entities the configured adult/child counts behave as before. Existing short-term forecast entities and the 1–120 minute forecast control remain unchanged. Learning storage remains compatible with v0.8.5.
