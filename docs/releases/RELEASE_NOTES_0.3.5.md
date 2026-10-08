# FreshAirIQ 0.3.5

## Fixed: rooms were not created after pressing Save

FreshAirIQ 0.3.4 changed only an in-memory working copy when a room was added.
The Config Entry was persisted only through the separate `finish` menu action.

0.3.5 changes the Options Flow so that **Save really saves**:

- Add room -> persists configuration -> closes Options Flow -> Home Assistant reloads FreshAirIQ
- Edit room -> persists -> reloads
- Remove room -> persists -> reloads
- Outdoor source and model settings follow the same immediate-save behavior

Existing rooms, learning storage and configuration are preserved.
