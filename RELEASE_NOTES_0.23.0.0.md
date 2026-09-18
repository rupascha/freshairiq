# FreshAirIQ 0.23.0.0 — Learning 3.0

## Shadow Learning
- Feuchte-Prognosekalibrierung wird nicht mehr nach jeder einzelnen Session direkt nachgeführt.
- Mehrere alternative Shadow-Multiplikatoren laufen parallel zum produktiven Modell und werden ausschließlich gegen reale, vergleichbare Session-Ergebnisse bewertet.
- Ein Shadow-Modell darf erst nach mindestens 8 belastbaren Proben, mindestens 12 % MAE-Verbesserung und mindestens 65 % Einzelsiegen übernommen werden.
- Pro Übernahme ist die Änderung des produktiven Feuchtefaktors auf maximal ±8 % begrenzt.

## Automatischer Rollback
- Jede Übernahme startet ein fünfprobiges Gegenfaktual-Fenster.
- FreshAirIQ vergleicht die neue Produktion mit dem vorherigen Faktor im Hintergrund.
- Ist das alte Modell wiederholt und mindestens 10 % besser, wird die Anpassung automatisch zurückgenommen.
- Nach Promotion oder Rollback verhindert ein Cooldown ein sofortiges Hin-und-Her-Lernen.

## Transparenz
- Raumdetails zeigen Learning-3.0-Status, Shadow-Phase, Übernahmen, Rollbacks und aktiven Rollback-Schutz.
- Diagnostik enthält ausschließlich technische Shadow-Metriken; keine personenbezogenen Daten werden ergänzt.

## Unverändert
- Lüftungsphysik, Sicherheitsgrenzen, Messkohärenz, Empfehlungen und Intelligence-2.0-Reifestufen bleiben unverändert.
- Temperatur-Feedback bleibt konservativ wie zuvor; Learning 3.0 übernimmt in dieser Version gezielt die Feuchte-Prognosekalibrierung.
