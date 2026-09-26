# FreshAirIQ 0.4.3

## Fixed: room visible in dashboard but missing under Devices & services

FreshAirIQ stores rooms in `ConfigEntry.data`. In v0.4.2 the new room was
persisted and immediately visible to the coordinator, so the dynamic dashboard
showed it. The already loaded Home Assistant entity platforms, however, still
used their previous room list.

v0.4.3 explicitly schedules a config-entry reload whenever structural data
changes. This rebuilds the sensor/binary_sensor platforms and therefore creates
or removes the corresponding room devices and entities immediately.

Affected operations:
- add room
- edit room
- remove room
- change outdoor-air source
