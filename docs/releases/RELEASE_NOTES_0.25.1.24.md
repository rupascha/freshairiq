# FreshAirIQ 0.25.1.25

## Support Diagnostics Client

FreshAirIQ can now prepare and submit a detailed support diagnostic directly to the FreshAirIQ Diagnostics Hub after explicit user confirmation. The submission dialog accepts an optional problem description, successful submissions start a persisted 60-minute cooldown, failed submissions do not consume the cooldown, and `support@freshairiq.com` remains the fallback support contact.

The receiving Hub endpoint is introduced separately in the matching Diagnostics Hub update. Until that server-side update is installed, the integration fails safely and does not start the cooldown.
