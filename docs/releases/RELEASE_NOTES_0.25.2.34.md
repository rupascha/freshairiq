# FreshAirIQ 0.25.2.34

## Notification compatibility

- Adds modern Home Assistant notify-entity delivery via `notify.send_message` and `target.entity_id`.
- Keeps legacy `notify.<service>` delivery fully compatible.
- Adds a manual test-notification action in the FreshAirIQ dashboard settings.
- Test delivery deliberately bypasses recommendation cooldown and quiet hours because it is explicitly initiated by the administrator.
- No notification target identifiers are added to exported diagnostics.
