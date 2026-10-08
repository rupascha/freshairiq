# FreshAirIQ v0.25.3.4 — Support & Settings Hotfix

- Correct direct `notify.send_message` entity targeting.
- Return a controlled 503 while the ConfigEntry runtime is still loading.
- Remove deprecated DeviceRegistry mapping access.
- Add search to multi-entity settings and filter new opening suggestions to window/door binary sensors while preserving configured legacy three-state helpers.
- Add `laundry_drying` as a selectable moisture source.
- Recover HTTP 409 enrollment conflicts by adopting an already persisted local credential for the same anonymous HA installation.
