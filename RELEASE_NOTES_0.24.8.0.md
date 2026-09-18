# FreshAirIQ 0.24.8.0

Runtime-lifecycle and Home Assistant action-hardening release.

## Änderungen

- Transactionaler Config-Entry-Unload: bei fehlgeschlagenem Plattform-Unload bleiben Listener und Runtime vollständig aktiv.
- `ConfigEntry.runtime_data` ist der bevorzugte Runtime-Pfad; `hass.data` bleibt nur als Kompatibilitätsfallback.
- `freshairiq.execute_intervention` nutzt native, übersetzbare Home-Assistant-Exceptions.
- Betriebsmodus-Select und Reset-Buttons liefern ebenfalls native übersetzbare Fehler.
- Legacy-Migration wird durch beschädigte Raumlisten, ungültige Raumzeilen, `nan`/Text-Kontaktverzögerungen oder defekte Alt-Schwellwerte nicht mehr blockiert.
- HA-Runtime-Teststruktur erweitert um Lifecycle-, Actions- und Migrationsfälle.

## Verifikation

- 503 lokale Regressionstests grün.
- 95,07 % Pure-Logic-Coverage, Gate >=95 %.
- HA-Runtime-Tests sind für den realen Home-Assistant-CI-Job vorgesehen; sie können in der lokalen Offline-Umgebung ohne installierten Home-Assistant-Paketbestand nicht ausgeführt werden.
