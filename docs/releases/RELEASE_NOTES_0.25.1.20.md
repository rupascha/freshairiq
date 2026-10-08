# FreshAirIQ 0.25.1.20

## User-controlled diagnostics sharing hotfix

Adds a second diagnostics action next to the existing export button. It creates the same detailed FreshAirIQ diagnostics JSON locally and opens the platform share sheet so the user can explicitly send the file to `support@freshairiq.com`. No manual support file is uploaded to the Diagnostics Hub. If file sharing is unavailable, FreshAirIQ downloads the JSON and opens a pre-addressed support e-mail with instructions to attach the exported file.

The previously drafted Hub-upload/cooldown path was removed before release.
