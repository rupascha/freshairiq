# FreshAirIQ 0.21.0.2 – Room Monitoring & Resident Profile Hotfix

- Monitor-only/structure rooms with configured temperature and humidity sensors now keep showing their real live sensor values without participating in recommendations, forecasts, learning, statistics or house balance.
- The room detail view now clearly distinguishes monitor-only rooms from calculated rooms and no longer renders misleading zero-valued forecast/learning cards for excluded rooms.
- Monitor-only rooms without valid sensors show a precise configuration/availability explanation instead of fabricated climate values.
- The missing "Grundlagen" icon now uses the broadly supported `mdi:home-outline` icon for improved frontend/WebView compatibility.
- Resident profiles are promoted as a distinct Personal FreshAirIQ Profile with a dedicated spotlight entry and stronger visual hierarchy.
- Existing physics, recommendation, forecast, safety and learning logic remains unchanged.
