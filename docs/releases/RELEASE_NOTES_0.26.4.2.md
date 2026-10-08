# FreshAirIQ 0.26.4.2

Fixes derived from the Diagnostics Hub export of 2026-10-08 (87 installations, 419 analysed batches).
- Privacy/diagnostics: free-text redaction replaced private labels as plain substrings. A floor named "1" was replaced inside every number, which corrupted support codes, fingerprints and timestamps on the Hub (e.g. `FAIQ-SENSOR-DATA-00level-…`) and created two bogus issue clusters. Labels are now replaced only as whole words, and purely numeric labels only when they are the entire value.
- Guardian: `FAIQ-GUARDIAN-SENSOR-002` ("unavailable sources require recovery guard", 45 findings in 24 installations) fired for every outage that lasted longer than the 90-second grace window, although leaving grace is intended there (the outage is then reported as a sensor error). It now fires only when the guard should still be running. The coordinator exposes `sensor_recovery.unavailable_for_seconds` for this; golden master re-recorded after verifying that this key is the only output change.
- Dashboard (community): rooms named "Wohnzimmer" showed the kitchen pot icon. Kitchens keep it, living rooms get a sofa; a room icon chosen in the room settings still wins.
- Dashboard (community: "where did the settings go, the gear is gone?"): admins get the settings gear back in the details header. It opens the dashboard settings centre, which had no visible entry point any more.
- UI contract hashes re-baselined for these approved changes.

## Known limits
- Tested in Chromium and with the coordinator golden master, not on a real Home Assistant instance.
