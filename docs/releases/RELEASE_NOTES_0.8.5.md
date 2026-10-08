# FreshAirIQ v0.8.5 – Intelligent Forecast

## Neu

- Die starre 5-Minuten-Schätzung wurde im Dashboard durch eine adaptive Kurzzeitprognose ersetzt.
- Der Prognosezeitraum ist frei von **1 bis 120 Minuten** einstellbar; Schnellwerte: 5, 10, 13, 15, 20, 30 und 60 Minuten.
- Neue Home-Assistant-Entität: **Prognosezeitraum** (`number`) zur persistenten Einstellung des Horizonts.
- Die Prognose zeigt gemeinsam: **Feuchteänderung in ml**, **Temperaturänderung in °C**, **Wiederaufheizkosten in €** und **Modellvertrauen**.

## Prognosemodell

Die neue Hybridprognose kombiniert:

- aktuelle absolute Feuchte innen und der Referenz-/Außenluft,
- gelernten Luftaustausch jedes Raums,
- aktuelle Fenster-/Türzustände,
- Querlüftung, Wind und Fensterausrichtung über den Luftstromfaktor,
- Verlauf der **absoluten** Feuchte statt nur relativer Feuchte,
- beobachtete interne Feuchtequellen/-senken und Feuchtepufferung,
- Bewohner-/Haushaltsmodell als Prior,
- gemessene thermische Raumreaktion,
- Heizsystem, Wirkungsgrad/COP und Energiepreis.

Während einer laufenden Lüftung trennt FreshAirIQ den theoretischen Lüftungseffekt vom tatsächlich gemessenen Nettoverlauf. Steigt die Wassermenge trotz trockener Außenluft, wird der daraus abgeleitete interne Feuchteeintrag gelernt und kann die Prognose auf **+ ml** drehen.

## Energie

Für längere Prognosezeiträume wird die Wiederaufheizenergie jetzt kumulativ über das ausgetauschte Luftvolumen berechnet. Die Konzentrations-/Feuchteprognose darf sich weiterhin asymptotisch der Außenluft annähern, die Heizlast wird bei fortgesetztem Luftaustausch jedoch nicht künstlich auf ein Raumvolumen begrenzt.

## Kompatibilität

Die bestehenden 5-Minuten-Sensorfelder bleiben erhalten, damit bestehende Automationen nicht brechen. Das integrierte FreshAirIQ-Dashboard verwendet die neue dynamische Prognose.
