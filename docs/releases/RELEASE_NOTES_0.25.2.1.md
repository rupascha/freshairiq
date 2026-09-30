# FreshAirIQ 0.25.2.1

## Support Diagnostics Deferred Error Telemetry Hotfix

- Failed explicit support-diagnostic uploads are retained locally as privacy-safe structured client errors.
- Retained errors are replayed after the next successful diagnostics Hub contact.
- Existing 60-minute support cooldown behavior is unchanged and begins only after a successful support upload.
