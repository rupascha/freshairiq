# FreshAirIQ 0.25.0.27 — Measurement & Validation Hardening Hotfix

- Trennt adaptive Lernmessungen von der strengeren objektiven Prognosevalidierung.
- Eine objektive Startprognose wird erst an einem zeitlich belastbaren A/B-Messrahmen eingefroren.
- Startprognose, reale Vergleichsdauer und Ergebnis verwenden jetzt dieselbe Validierungs-Zeitbasis.
- Der physische Lüftungswert bleibt unverändert; für die Prognosebewertung wird zusätzlich ein eigener zeitgleicher Validierungswert geführt.
- Ein A/B-Endmessrahmen aus den letzten 120 Sekunden vor dem Schließen darf als enger Close-Fallback dienen; ältere/held Messungen werden nicht objektiv bewertet.
- Bestehende AH-, Empfehlungs-, Threshold-, Dashboard- und adaptive Lernlogik bleibt ansonsten unverändert.
