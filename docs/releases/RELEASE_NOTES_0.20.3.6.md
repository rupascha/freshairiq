# FreshAirIQ 0.20.3.6

Stabilitäts-Hotfix für Prognose- und Lernlogik.

- Physische Fensteröffnungszeit und Messbaseline werden getrennt geführt. Laufzeit, Empfehlung und Forecast-Scoring verwenden die reale Öffnungszeit; Feuchte-Lernen verwendet ausschließlich die zeitlich passende Messbaseline.
- Startprognosen werden nur noch bei enger Zeitübereinstimmung bewertet: 10 % des Horizonts, mindestens 1 und höchstens 2 Minuten Toleranz.
- Sehr große Prognoseausreißer verändern das Modell beim ersten Auftreten nicht mehr. Erst eine ähnliche zweite Probe führt zu einer sehr vorsichtigen Anpassung; ab wiederholter Bestätigung wird das Muster kontrolliert übernommen.
- Diagnose- und Ergebnisdaten weisen die neuen Zustände nachvollziehbar aus.
