# FreshAirIQ 0.3.7

## Fixed: fully orphaned deleted room devices

The 0.3.6 cleanup only searched devices still associated with the FreshAirIQ
Config Entry. With Home Assistant 2026.8+ device ownership changes, a deleted
room can already be detached from that Config Entry while still remaining in
the Device Registry.

0.3.7 scans the complete Device Registry for FreshAirIQ's stable room identifier:

`(freshairiq, "<config_entry_id>:room:<room_key>")`

For every room identifier that no longer exists in FreshAirIQ configuration it:
1. removes all attached entity-registry entries, including disabled entities;
2. removes the orphaned device.

This also cleans ghost rooms left behind by earlier FreshAirIQ versions.
