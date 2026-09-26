# FreshAirIQ 0.25.0.28 – Android Details Scroll & Delayed Learning Explanation Hotfix

- Android/Touch: Die vertikale Touch-Geste wird nicht mehr am Modal-Overlay mit `touch-action:none` abgeschnitten. Overlay, Dialog und der bestehende `.dialog-scroll`-Bereich erlauben jetzt eine durchgängige vertikale Pan-Geste; der feste Header und die getrennte Scrollfläche bleiben erhalten.
- Lüftungsauswertung: Bei zeitversetzt meldenden Sensoren erklärt FreshAirIQ nun ausdrücklich, dass auf einen belastbaren Messvergleich gewartet wird und die Lern-Auswertung deshalb verzögert erscheinen kann.
- Keine Änderung an AH-/ml-Berechnung, Recommendation Engine, Schwellenwerten, Prognoseformel oder Lernentscheidung.
