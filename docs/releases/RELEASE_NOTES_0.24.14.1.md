# FreshAirIQ 0.24.14.1 — Startprognose- & Einstellungs-Hotfix

## Geändert

- Startprognosen werden beim bestätigten Lüftungsbeginn als unveränderlicher Startzustand eingefroren.
- Beim Lüftungsende wird dieser Startzustand auf exakt die tatsächlich gemessene Lüftungsdauer ausgewertet. Dadurch entfällt der systematische Konflikt zwischen z. B. einer 15-Minuten-Prognose und einer realen 9- oder 25-Minuten-Lüftung.
- Langsam meldende Batterie-Sensoren verhindern die Startprognose nicht mehr. Ein zeitgleicher Vergleich darf angezeigt werden; für Modelllernen und objektive Validierung bleiben weiterhin nur ausreichend synchronisierte Messrahmen zugelassen.
- Die IQ-Auswertung unterscheidet jetzt klar zwischen zeitgleichem Informationsvergleich und für das Lernen verwertbarer Prognosevalidierung.
- Veraltete Options-Flow-Routen `house` und `personalisation` zeigen keine doppelten Einstellungsformulare mehr, sondern führen in die kanonischen Bereiche Gebäude/Bewohner. Bereits geöffnete alte Formulare werden beim Absenden weiterhin akzeptiert.

## Unverändert

- Lüftungsphysik, Feuchteformeln, Forecast-Modellkoeffizienten und bestehende Empfehlungsgrenzen wurden nicht verändert.
- Die in 0.24.14.0 eingeführten optionalen VOC/TVOC-, PM2.5- und Helligkeitssensoren sowie deren Diagnostik bleiben erhalten.
