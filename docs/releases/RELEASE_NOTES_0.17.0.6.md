# FreshAirIQ v0.17.0.6 – Sofort-Schließen Hotfix

Basis: v0.17.0.5.

## Geändert
- Eine finale `close`-Entscheidung behält jetzt immer `duration_min = 0.0`.
- Die konfigurierte Mindestlüftungsdauer wird ausschließlich auf weiterhin laufende bzw. neu empfohlene Lüftung angewendet.
- Dadurch kann eine fachlich bereits getroffene Empfehlung „Jetzt schließen“ nicht mehr durch die finale Konsolidierung in zusätzliche Lüftungsminuten umgewandelt werden.

## Unverändert
- Zwei-Messwerte-/15-Minuten-Schließfreigabe aus v0.17.0.5
- Prognose-, Lern-, Pollen-, Schimmel-, Querlüftungs- und UI-Logik
