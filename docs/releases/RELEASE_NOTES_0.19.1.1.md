# FreshAirIQ 0.19.1.1 — Schließlogik-Hotfix

Dieser Hotfix korrigiert ausschließlich die Schließentscheidung laufender Lüftungen.

- Ziel-RH bzw. Schließdifferenz lösen nicht mehr allein eine Schließempfehlung aus, solange der kurzfristige 5-Minuten-Feuchteertrag noch relevant ist.
- Bei mehreren geöffneten Räumen wird zusätzlich der kombinierte kurzfristige Restnutzen geprüft.
- Die konfigurierte Maximaldauer und eine klar schlechte thermische Effizienz bleiben eigenständige Schließgründe.
- Eine finale Schließempfehlung zeigt keine positive Restzeit mehr an.

Keine sonstigen Funktionen, Einstellungen oder Dashboard-Bereiche wurden absichtlich verändert.
