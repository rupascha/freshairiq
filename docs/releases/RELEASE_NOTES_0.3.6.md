# FreshAirIQ 0.3.6

## Fixed: deleted room remained as an unavailable device

Home Assistant keeps entity/device registry records even after an integration stops
providing those entities. In FreshAirIQ 0.3.5 this caused a deleted room to remain
visible with all sensors marked unavailable.

0.3.6 performs registry reconciliation during setup:

1. Read all room keys currently configured in FreshAirIQ.
2. Find FreshAirIQ room devices registered for this config entry.
3. For devices whose room key no longer exists, remove their FreshAirIQ entity-registry entries.
4. Remove the orphaned room device.

This also cleans already existing ghost rooms from older versions after the next
FreshAirIQ reload or Home Assistant restart.
