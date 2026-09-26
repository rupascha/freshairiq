# FreshAirIQ 0.20.1.4

Hotfix für plattformübergreifende Dashboard-Stabilität.

- Details-Dialog verwendet nun einen eigenen, gekapselten Scroll-Container. Die feste Kopfzeile bleibt oben und Inhalte können nicht mehr hinter/über die Kopfzeile hinaus scrollen.
- Die Lüftungsprognose weist bei einer Feuchteziel-Begrenzung zeigt die laufende Lüftung als Hauptwert die tatsächlich modellierte physische Wirkung des gewählten Zeitraums. Der für die Entscheidung relevante, am Feuchteziel begrenzte Nutzen wird darunter separat ausgewiesen. So reagieren 15/30/60 Minuten sichtbar unterschiedlich, ohne die Schließ-/Sicherheitslogik zu verändern.
- Frontend-Kompatibilität für ältere WebViews/iPads verbessert: Objekt-Spreads im Laufzeitcode entfernt, DOM-Collections kompatibel konvertiert und Live-Patching von browserabhängigen instanceof-/Node-Konstanten entkoppelt.
- Keine Änderung der Sicherheits-, Lern- oder Lüftungsentscheidungslogik.
