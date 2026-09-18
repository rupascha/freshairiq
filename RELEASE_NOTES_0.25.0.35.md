# FreshAirIQ 0.25.0.35 – Passive-Open UI Hotfix

Dieser Hotfix korrigiert ausschließlich die Darstellung und Weitergabe des bereits vorhandenen `passive_open_monitor`-Zustands. Die Erkennung selbst und die physikalische Lüftungslogik wurden nicht verändert.

- Lange, stabile Öffnungen werden weiterhin als wahrscheinliche Dauer-/Kippöffnung erkannt.
- Der Decision Brain erhält dafür eine eigene Darstellung statt der generischen „keine Aktion / Fenster geschlossen lassen“-Ansicht.
- Die Dashboard-Karte zeigt den Monitoring-Zustand klar und ersetzt „+X min über Ziel“ durch „Daueröffnung wird überwacht“.
- Werden Temperatur, Feuchtebilanz oder Außenbedingungen ungünstig, fällt die bestehende Logik wieder auf die normale Schließentscheidung zurück.
