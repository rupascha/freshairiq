# FreshAirIQ 0.24.0.0 — Room Climate Intervention Foundation

## Neu
- Optionale Raumluft-Sensorik: VOC/TVOC, PM2.5 und Helligkeit.
- Optionale Raumklima-Aktoren pro Raum: Rollos/Jalousien, Klima, Abluft, Zuluft,
  Lüftungs-/WRG-Geräte, Entfeuchter, Befeuchter und Luftreiniger.
- Neue Intervention Engine bewertet vorhandene Geräte zusätzlich zur bestehenden
  Fensterlüftungslogik, ohne Forecast-, Session- oder Learning-Physik zu verändern.
- Jede Maßnahme enthält Priorität, Begründung und – nur wenn konservativ möglich –
  eine explizite Home-Assistant-Aktion.
- Neue Aktion `freshairiq.execute_intervention`: führt nur auf ausdrücklichen Aufruf
  die aktuell berechnete ausführbare Maßnahme eines Raums aus. Keine automatische
  Gerätebetätigung im Hintergrund.

## Sicherheitsprinzipien
- Bestehende Lüftungsentscheidung bleibt die kanonische Quelle für Fensterlüftung.
- Klimageräte erhalten keine automatisch erfundenen Sollwerte oder HVAC-Modi.
- Nicht ausführbare oder unsichere Maßnahmen bleiben reine Empfehlungen.
- Neue optionale Entitäten sind vollständig rückwärtskompatibel; ohne Konfiguration
  verhält sich FreshAirIQ wie 0.23.0.11.
