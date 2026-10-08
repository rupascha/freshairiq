# FreshAirIQ 0.9.8.0 — Routine Intelligence

Phase 4 erweitert die bestehende Intelligence Engine um langfristiges Bewohner- und Routinenlernen, ohne die funktionierende v0.9.7.0-Physik zu ersetzen.

## Neu
- Zeitabhängiges Feuchtequellen-Lernen pro Raum (Werktag/Wochenende × Stunde).
- Zeitabhängiges Lernen, wann Empfehlungen typischerweise befolgt werden.
- Routine-IQ mit konservativer Lernreife; wenige Messungen beeinflussen keine Entscheidungen.
- Decision Engine v3 berücksichtigt erwartete Feuchteproduktion beim Vergleich von 15/30/60-Minuten-Warteoptionen.
- Nachtprognose kann ein ausreichend reifes Routinenmodell vorsichtig mit dem bestehenden Anwesenheits-/Nachtmodell verbinden.
- Raumdetails zeigen kompakt Routine-Reife, Probenzahl und die aktuell erwartete interne Feuchtequelle.
- IQ-Aktivität kann „Tagesroutinen berücksichtigt“ anzeigen.

## Sicherheits-/Stabilitätsprinzip
- Keine festen Tagesabläufe oder Nutzungszeiten werden angenommen.
- Fehlende/noch unreife Routinedaten fallen automatisch auf das bisherige Modell zurück.
- Gelernte Bewohnergewohnheiten dürfen physikalische bzw. Gesundheitsgrenzen nicht überschreiben.
- Bestehende Forecast-, Wetter-, Presence-, Lüftungs- und Outcome-Lernlogik bleibt erhalten.
