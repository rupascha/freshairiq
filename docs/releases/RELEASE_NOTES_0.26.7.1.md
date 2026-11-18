# FreshAirIQ 0.26.7.1

Hotfix nach 0.26.7.0. Keine Änderung an Entity-IDs, Services, Ereignissen oder dem Raumaktions-Vertrag; neue Felder
sind optional und additiv. Enthält die intern als 0.26.7.1 und 0.26.7.2 gelieferten Arbeitsstände (nie
veröffentlicht); öffentliche Versionsnummer ist 0.26.7.1.

## IQ2 – neues Prognose-, Lern- und Entscheidungsmodell
- Schließen bei erreichtem Ziel ist jetzt der Standard: Sind die aktiven Ziele eines Raums verlässlich erreicht
  (z. B. nur „Entfeuchten“ und die Luftfeuchte liegt am Ziel), empfiehlt FreshAirIQ das Schließen – auch wenn die
  Außenluft noch trockener ist. Wer weiterentfeuchten möchte, wählt im Raum „Weiterentfeuchten, solange die Außenluft
  Feuchte abführt“. Raum- und Hausempfehlung widersprechen sich dabei nicht mehr.
- „Weitere N min“ zeigt die erwartete Änderung der Raumluft; „bis zum Feuchteziel noch“ steht getrennt daneben.
  Eine Null bis zum Ziel bedeutet „Ziel erreicht“, nicht „Lüften wirkt nicht“.
- Die Temperaturprognose berücksichtigt die Wärmespeicherung des Raums (keine unrealistischen −9 °C mehr).
- Das Lernen rechnet den Luftwechsel jetzt für jede Lüftungsdauer gleich zurück, nutzt das Wissen des ganzen Hauses
  für neue Räume und bewertet jede Prognose gegen die Messung. „Prognosesicherheit“ heißt jetzt „Lernreife“; der
  Erwartungsbereich der Prognose erscheint erst, wenn er an den eigenen Lüftungen kalibriert ist.
- Hauskarte: Restzeit je Raum kommt von der Integration („jetzt schließen“, „Mindestdauer noch …“, „wird neu
  bewertet“) – keine Restzeit mehr aus einem alten Plan.
- Lüfter-Automatik: stoppt mit dem Standard bei erreichtem Feuchteziel; mit „Weiterentfeuchten“ wie bisher.
- Hinweis: Die Verbesserungen sind in Simulationen geprüft, noch nicht an Felddaten. Einzelheiten und Grenzen:
  `docs/IQ2.md`.

## Entscheidung und Zeiten
- Eine erreichte, ausdrücklich eingestellte Temperaturgrenze beim Lüften schließt zuverlässig – auch bei laufender
  Dusche und bei zwei offenen Luftwegen; kein Overlay macht daraus „weiterlüften“. Kritisches CO₂ behält Vorrang.
- Ein gehaltener Schließhinweis behält seinen Grund: nur tatsächlich erreichte Ziele werden als „erreicht“ gehalten.
- „0 min“ nur bei echtem Schließen; sonst „wird neu bewertet“ mit gemessenem Grund. Zielbegrenzte Prognosen zeigen
  zusätzlich den physikalischen Wert.
- Optional je Raum: eigene Temperaturgrenze beim Lüften; Schließstrategie siehe IQ2 oben.

## Bedienung
- Feedback: Entwurf je Eintrag und Typ, Quittung und Sperre gehören zum gesendeten Eintrag; Hauskarte nutzt denselben
  Speicher. Saisonkarte nennt Beobachtungstage, Mindestmenge und fehlende Saisonabdeckung getrennt.

## Update von einem 0.26.7.2-Teststand
Wer einen nicht veröffentlichten 0.26.7.2-Teststand installiert hat, bekommt 0.26.7.1 nicht automatisch angeboten
(kleinere Nummer). Weg: in HACS „Neu herunterladen“ und Version 0.26.7.1 wählen (oder `freshairiq.zip` des Releases
nach `custom_components/freshairiq` entpacken), danach Home Assistant neu starten. Die Karten laden über die geänderte
Versionskennung neu; gespeicherte Daten bleiben kompatibel (neues Feld `close_notified_kind` wird ergänzt).
