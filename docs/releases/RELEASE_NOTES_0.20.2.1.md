# FreshAirIQ 0.20.2.1

## Hotfix: rollierende Langzeit-Prognose

Dieser Hotfix verändert ausschließlich die nutzergewählte Lüftungsprognose für Horizonte über 5 Minuten. Die etablierte interne 5-Minuten-Schließ-/Weiterlüften-Logik bleibt unverändert.

### Geändert
- 15–120-Minuten-Prognosen werden jetzt in 5-Minuten-Schritten simuliert.
- Jeder Simulationsschritt startet mit dem vorhergesagten Raumzustand des vorherigen Schritts. Dadurch entwickeln sich Feuchtegradient, Raumtemperatur und interne Feuchtebeiträge realistisch über den Prognosezeitraum weiter.
- Wenn der Raum die Außenluft als Referenz nutzt und eine Home-Assistant-Wetterprognose verfügbar ist, werden interpolierte zukünftige Außenwerte für jeden 5-Minuten-Schritt berücksichtigt.
- Bei eigener Referenzsensorik bleibt die Referenz bewusst konstant, da FreshAirIQ für diese Quelle keine belastbare Zukunftsprognose besitzt.
- Live-Messdaten einer laufenden Lüftung werden nicht mehr linear über 60 Minuten fortgeschrieben. Ihr Einfluss wird schrittweise auf den jeweils erwarteten zukünftigen Zustand angewendet.
- Die Prognose stellt intern Diagnosewerte zur Simulationszahl, erwarteten Endfeuchte und Wetterverwendung bereit.

### Unverändert
- Die interne 5-Minuten-Steuerprognose und damit die bestehende Schließ-/Weiterlüften-Sicherheitslogik.
- Konfiguration, Sensorzuordnung, Feuchtequellenlogik, Nachtstrategie und sonstige FreshAirIQ-Funktionen.
