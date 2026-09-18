# FreshAirIQ 0.9.4.6 – Forecast Consistency Hotfix

Gezielter Hotfix auf Basis von 0.9.4.5. Die funktionierende Live-Feuchtebilanz während laufender Lüftungen bleibt unverändert.

## Behoben
- Die frei wählbare Prognose (5–120 min) und die intelligente Empfehlung verwenden nun dieselbe Forecast Engine.
- „Weitere 5 Minuten“ kann nicht mehr aus einer anderen Berechnungslogik stammen als „Weitere 60 Minuten“.
- Der angezeigte Lüftungseffekt beschreibt die durch Luftaustausch entfernte bzw. eingetragene Feuchte und ist bei unveränderten Randbedingungen über längere Horizonte konsistent.
- Gelernte interne Feuchtequellen/Sorption bleiben als separater Netto-Diagnosewert erhalten und verfälschen nicht mehr die Beschriftung „entfernt“.
- Die Hauskachel „ENTFERNBAR“ entspricht nun der Summe der im Raum-Popup angezeigten entfernbaren Raum-Potenziale.
- Die Entscheidungslogik bleibt getrennt: Schwellen und Empfehlungen verwenden weiterhin nur tatsächlich lüftungsrelevante Räume.
