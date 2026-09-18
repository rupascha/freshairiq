# FreshAirIQ 0.25.0.8 – Validation Accuracy Hotfix

Gezielter Hotfix auf Basis von 0.25.0.7.

## Behoben

- Die IQ-Auswertung zeigt keine Prozent-Genauigkeit mehr, wenn eine zeitlich angeglichene Startprognose wegen unsynchroner Start-/Endmessdaten nicht objektiv validierbar ist.
- Eine eingefrorene Startprognose wird weiterhin auf die tatsächlich gemessene Lüftungsdauer ausgewertet; rollierende Restprognosen werden nicht als Startprognose verwendet.
- Hausweite Prozentwerte werden nur noch veröffentlicht, wenn alle beitragenden zeitlich angeglichenen Sessions den strengen Vergleich bestehen. Teilvergleiche bleiben ausschließlich Diagnoseinformation.
- Nicht objektiv vergleichbare Prognose-Sessions sind nun auch für das Prognose-Lernfeedback gesperrt.
- Die Dashboard-Karte verwendet für Prognosegenauigkeit ausschließlich die strengen `prediction_*`-Werte und fällt nicht mehr auf informative `aligned_*`-Werte zurück.

Keine Änderungen an Lüftungsempfehlungen, Feuchtephysik, Prognosemodellformeln, Sensorzuordnung oder Dashboard-Struktur außerhalb dieser Validierungs-/Darstellungslogik.
