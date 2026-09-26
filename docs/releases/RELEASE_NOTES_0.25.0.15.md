# FreshAirIQ 0.25.0.15 — Evidence-Time Learning Hotfix

- Lernreife trennt Messpunktmenge von unabhängiger Erfahrung.
- Tagesroutinen reifen über unterschiedliche beobachtete Tage statt Polling-Samples.
- Nachtmodell zählt für die Reife jede reale Nacht höchstens einmal; Ziel für volle Reife: 120 unterschiedliche Nächte.
- Saisonalität wird in Frühling, Sommer, Herbst und Winter getrennt bewertet.
- Eine Jahreszeit gilt nur als vollständig durchlaufen, wenn brauchbare Beobachtungen nahe Saisonanfang und -ende sowie an mindestens 60 unterschiedlichen Tagen vorliegen.
- Die höchste saisonale Stufe ist zusätzlich vor 365 Tagen realer Kalenderabdeckung gesperrt und verlangt alle vier vollständig beobachteten Jahreszeiten.
- Bestehende Roh-Lernwerte bleiben erhalten; alte Sample-Zähler werden nicht fälschlich in Tage/Nächte umgedeutet.
- Dashboard benennt die jeweilige Evidenzeinheit (Tage, Nächte, Vergleiche, Lüftungen) statt pauschal „Proben“.
