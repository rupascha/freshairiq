# FreshAirIQ v0.25.1.36 — Atomic Room Creation Hotfix

- Native room creation is now transactional across Home Assistant subentry state and FreshAirIQ canonical room data.
- Parent room data is written only after the Home Assistant subentry exists.
- Structural reload happens only after that verified commit.
- Failed room flows leave neither duplicate nor ghost parent rooms.
- Existing room, ventilation, forecast, learning, recommendation and dashboard behavior is unchanged.
