# FreshAirIQ 0.9.6.0 – Decision & Simulation Engine

## Neu
- Zentrale Decision & Simulation Engine bewertet mehrere Handlungsoptionen statt nur einen momentanen Zustand.
- Simuliert, sofern sinnvoll: jetzt lüften, 15/30/60 Minuten warten und Nacht abwarten.
- Bewertungspriorität: Gesundheit/Schimmel zuerst, danach Komfort und Energie.
- Bewohnerlernen beeinflusst die empfohlene Lüftungsdauer konservativ, sobald genügend abgeschlossene Sitzungen vorhanden sind.
- Jede Entscheidung enthält eine Optionsmatrix mit Score, Feuchtewirkung, Temperaturänderung, Kosten, Confidence und verwendeter Annahme.
- Zukünftige Außenluft wird nicht erfunden: solange keine echte Zukunfts-Wettergrenze vorliegt, werden Warteoptionen ausdrücklich konservativ mit aktuellen Außenbedingungen bewertet.
- Hysterese verhindert, dass die Hauptempfehlung zwischen „jetzt“ und „warten“ flattert.

## Kompatibilität
Die bestehende v0.9.5.0 Raum-, Forecast-, Lern- und Recommendation-Logik bleibt erhalten. Die neue Decision Engine sitzt darüber und verfeinert nur die zentrale Empfehlung.
