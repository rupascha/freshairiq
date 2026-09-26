# FreshAirIQ 0.20.1.5

Hotfix für Details-Scrolling, laufende Kurzzeitprognose, Ergebnislernen und IQ-Zeit.

- Das Details-Fenster verwendet jetzt dieselbe robuste Struktur wie die Raumfenster: feste Kopfzeile plus separater Scrollbereich.
- Während einer laufenden Lüftung wird die Kurzzeitprognose nach genügend echten Sensorupdates zunehmend mit dem zuletzt gemessenen Feuchteabbau abgeglichen. Ein theoretisch hoher Luftaustausch darf eine real stagnierende Lüftung dadurch nicht mehr überstimmen.
- Früh in einer Lüftung bleibt das physikalische Modell dominant; reale Messdaten gewinnen erst mit Zeit und bestätigten Sensorwerten an Gewicht.
- Nach Abschluss erklärt die IQ-Auswertung, ob die Messabweichung regulär, vorsichtig oder nur minimal in zukünftige Prognosen einfließt.
- Sehr große Abweichungen werden absichtlich nur minimal gelernt, damit ein einzelner Ausreißer das Modell nicht verzieht.
- Die IQ-Zeit zeigt bei überschrittener Zieldauer die tatsächliche Überschreitung statt `+0 min`.
