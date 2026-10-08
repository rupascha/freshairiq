# FreshAirIQ 0.23.0.3

Hotfix for intermittent Home Assistant “Configuration error” cards, especially on cold iPhone/iPad WebView starts.

The tiny FreshAirIQ bootstrap is now registered through Home Assistant's global frontend path in addition to the canonical storage-mode Lovelace resource. Both paths use the exact same versioned ES-module URL, which lets the browser deduplicate execution while increasing the chance that `freshairiq-card` and the FreshAirIQ dashboard strategy are defined before Home Assistant constructs the dashboard.

No calculation, recommendation, learning, forecast, room configuration, or UI layout behavior was intentionally changed.
