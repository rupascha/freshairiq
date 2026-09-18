# FreshAirIQ v0.17.0.2 – Prognoseberechnung Hotfix

Hotfix ausschließlich für die Prognoseberechnung auf Basis von v0.17.0.1.

- Lange frei wählbare Lüftungsprognosen (> 5 min) werden bei Entfeuchtung am konfigurierten Raum-Feuchteziel begrenzt. Dadurch werden keine unrealistisch hohen Entfeuchtungswerte mehr ausgewiesen, nachdem das eigentliche Lüftungsziel bereits erreicht wäre.
- Die etablierte 5-Minuten-Live-Coach-Berechnung bleibt unverändert und beeinflusst die Schließen-/Weiterlüften-Logik daher nicht.
- Die Mehrstundenplanung behandelt erwartete interne Feuchteproduktion nicht mehr zu 100 % als später entfernbar. Sie rechnet die erzeugte Feuchte jetzt über den aus dem aktuellen Raumzustand abgeleiteten realistischen Luftwechselanteil in tatsächlich lüftungswirksames Potenzial um.
- Dadurch werden überhöhte Warteprognosen wie mehrere Liter vermeintlich entfernbarer Feuchte deutlich gedämpft, ohne die Wetter-, Routine- oder Lernmodelle abzuschalten.

Keine UI-, Raum-, Sensor-, Schimmel-, Pollen- oder Schließlogik wurde in diesem Hotfix geändert.
