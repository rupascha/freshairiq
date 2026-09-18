# FreshAirIQ 0.25.0.9 – Battery-Sensor Learning Hotfix

Gezielter Folge-Hotfix auf Basis von 0.25.0.8.

## Behoben

- Die strenge Prognosegenauigkeit bleibt unverändert: Nur `excellent`/`acceptable` Start- und Endmessrahmen dürfen eine Prozent-Genauigkeit erzeugen.
- Das adaptive Prognoselernen ist wieder bewusst von dieser strengen Genauigkeitswertung getrennt.
- Messrahmen mit Qualität `held` dürfen wieder vorsichtig ins Prognose-Lernfeedback einfließen. Die bereits vorhandene reduzierte Gewichtung von 35 % bleibt bestehen.
- `uncertain` und `stale` bleiben für dieses Prognose-Lernfeedback ausgeschlossen.
- Eine zeitlich auf die tatsächliche Lüftungsdauer abgeglichene Startprognose bleibt zwingende Voraussetzung; rollierende Restprognosen werden weiterhin nicht als Startprognose gelernt.
- Die Dashboard-Texte unterscheiden nun sauber zwischen fehlender objektiver Genauigkeitswertung und einem gegebenenfalls trotzdem vorsichtig möglichen Lernfeedback.

Keine Änderung an Lüftungsphysik, Empfehlungsschwellen, Forecast-Formeln, Sensorzuordnung oder der strengen Validierungslogik aus 0.25.0.8.
