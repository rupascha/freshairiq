# FreshAirIQ v0.9.3 – Status Entity & Room Data Hotfix

- Behebt die Auswahl einer veralteten/duplizierten `sensor.freshairiq_status`-Entität im Dashboard.
- Die Karte wählt nun den FreshAirIQ-Statussensor mit dem vollständigsten aktuellen Datensatz (Räume, Hauswasser, Bewohnerdaten) statt die kanonische Entity-ID blind zu bevorzugen.
- Dadurch werden Räume, Wasser in der Hausluft, Lüftungsschwelle, Nachtprognose und Presence Intelligence wieder aus dem aktiven Config Entry gelesen.
- `water_history_14d` wird nun ebenfalls als Statusattribut bereitgestellt, damit die neue Hauswasser-Statistik nicht leer bleibt.
- Keine Änderung an Recommendation-, Forecast-, Presence-, Energie-, Lern- oder physikalischer Berechnungslogik.
