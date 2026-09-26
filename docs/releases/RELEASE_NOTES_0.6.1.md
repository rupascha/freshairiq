# FreshAirIQ 0.6.1 — Korrektur 2.0

- Himmelsrichtung jetzt **je Lüftungskontakt/Fenster** konfigurierbar; Eckräume mit mehreren Fassaden werden unterstützt.
- Räume lassen sich direkt auf eine gewünschte Dashboard-Position setzen statt nur schrittweise hoch/runter zu verschieben.
- Neustart-Härtung: Sessions starten nie mehr mit Platzhalterwerten; beschädigte alte Session-Baselines werden bei plausiblen Messwerten sauber neu gesetzt. Das verhindert extreme Temperaturwerte nach einem HA-Neustart.
- Detailansicht behält bei Live-Aktualisierungen ihre Scrollposition.
- Hauptmetriken sind anklickbar und erklären Berechnung/Bedeutung; Raumkacheln öffnen zusätzliche Raumdetails.
- Betriebsprofil bleibt auch auf schmalen Displays oben rechts.
- Neue adaptive Lüftungsschwelle skaliert mit Haus-/Wohnungsgröße und Feuchteproduktion und zielt auf ca. 3–5 sinnvolle Lüftungen pro Tag. In der warmen Jahreszeit werden kühle Morgen-/Abendfenster bevorzugt.
- Migration von 0.6.0 übernimmt vorhandene Räume/Lernwerte; die alte unveränderte 10-%-Standardschwelle wird auf den neuen adaptiven Modus umgestellt.
