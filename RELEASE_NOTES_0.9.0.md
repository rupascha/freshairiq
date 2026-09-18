# FreshAirIQ v0.9.0 — Requirements Release

Diese Version setzt den Anforderungskatalog vom 09.09.2026 als zusammenhängende Entwicklungsstufe um.

## 20 Anforderungen

1. **Eine priorisierte Hauptempfehlung:** Recommendation Engine v3 liefert Handlung, Begründung, Feuchteeffekt, Temperaturänderung, Wiederaufheizkosten und Forecast-IQ aus demselben Zustandsmodell.
2. **Pollen nur bei aktivierter Option:** bei deaktivierter Pollenfunktion werden Pollendaten nicht als Veto oder Prioritätsfaktor verwendet.
3. **Konkrete Querlüftung:** konfigurierte Öffnungspaare werden als ausführbare Strategie mit Räumen/Kontakten und Dauer ausgegeben.
4. **Wind + Ausrichtung:** bestehender richtungsabhängiger Airflow-Faktor bleibt Bestandteil von Auswahl, Dauer und Forecast.
5. **Nichtlineare Prognose:** exponentiell sättigender Luftaustausch und gedämpfte Residuen verhindern lineare Langzeit-Hochrechnung.
6. **Laufenden Erfolg berücksichtigen:** Forecast startet stets vom aktuellen AH-/Temperaturzustand und berücksichtigt Session-Verlauf/Lernresiduen.
7. **Empfehlung = Prognose:** Hauptempfehlung trägt Forecast-Temperatur, Kosten und Confidence direkt mit; Schließen/Weiterlüften nutzt denselben Grenznutzen.
8. **Stabilisierungsphase:** nach dem Schließen gilt standardmäßig 4 min adaptive Sperrphase gegen sofortige Neuempfehlungen.
9. **Lüftungshistorie:** letzter Abschluss je Raum wird persistent gespeichert und in Wiederempfehlungen einbezogen.
10. **Mindestnutzen:** während des Wiederholungs-Cooldowns muss ein neuer Mindestnutzen überschritten werden.
11. **Bereiche/Ebenen:** frei benennbar, editierbar/zuordenbar und in Raumdarstellung/Engine-Daten enthalten.
12. **Querlüftung zonenplausibel:** Paare funktionieren standardmäßig nur in derselben Ebene/Luftströmungszone; explizite Zonenverbindungen sind möglich.
13. **Bewohner ohne Tracker:** Presence Intelligence liefert eine verständliche Erklärung der Annahme.
14. **Primärtracker:** die Presence-Auswertung begrenzt Tracker auf die konfigurierte Bewohnerzahl; die UI behandelt die Liste als Primärzuordnung.
15. **Präsenzsensoren als weiche Evidenz:** optionale Binary-Sensoren erhöhen Wahrscheinlichkeit, ohne aus einem Einzelereignis einen sicheren Bewohner zu machen.
16. **Haustiermodus:** klassische Bewegung wird bei Haustieren stark abgewertet; als haustiersicher markierte Präsenzsensoren wiegen stärker.
17. **Scrollstabile Detailansicht:** Live-Neurendering wird während aktiver Touch-/Scroll-Interaktion gepuffert; Scrollposition wird erhalten.
18. **Hauswasser pro Tag:** persistentes Tagesmittel der gesamten Wassermenge in der überwachten Innenluft, inklusive Trend trocken/stabil/feuchter.
19. **Temperaturstatistik entfernt:** Statistikbereich fokussiert Hauswassermenge und Presence Intelligence.
20. **Drag-and-drop-Sortierung:** Räume und Bereiche verwenden Home-Assistant-Reorder-Selector und speichern die Reihenfolge persistent.

## Neue/erweiterte Optionen

- `post_ventilation_stabilization_min` (Standard 4 min)
- `repeat_recommendation_cooldown_min` (Standard 20 min)
- `repeat_min_benefit_ml` (Standard 80 ml)
- `presence_sensor_entities`
- `pet_safe_presence_entities`
- `pets_in_household`
- `cross_zone_connections`

## Migration

Bestehende v0.8.6-Konfigurationen bleiben nutzbar. Neue Optionen erhalten sichere Defaults; Lernwerte und laufende Statistiken werden nicht absichtlich verworfen.
