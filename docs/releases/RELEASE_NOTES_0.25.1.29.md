# FreshAirIQ v0.25.1.29 — HA Area Sensor Discovery

- Imports Home Assistant floors and areas without changing existing FreshAirIQ rooms.
- Prefills unambiguous room-local temperature, humidity, CO₂, illuminance and climate entities.
- Prefills window, door and opening contacts assigned to the imported area.
- Prefers Home Assistant's explicit area temperature/humidity entities.
- Resolves effective device areas, including inherited child-device areas.
- Keeps manual selection available and never overwrites existing assignments.
