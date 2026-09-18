# FreshAirIQ 0.18.0.4 — Consistency & Night Strategy Hotfix

Hotfix auf Basis von 0.18.0.3. Keine bestehende Kernfunktion wurde entfernt.

- Der frei gewählte Prognosezeitraum wird in nutzerseitigen Empfehlungen, Raum-Benachrichtigungen und Dashboard-Fallbacks durchgängig verwendet.
- Die interne 5-Minuten-Logik für Schließen/Live-Coach bleibt als Sicherheits-/Marginalcheck erhalten, wird aber klar als interner Schließcheck bezeichnet und nicht mit dem konfigurierten Prognosezeitraum verwechselt.
- Kontrollierte Nachtlüftung wählt konkrete Räume mit konfigurierten Lüftungskontakten aus und simuliert ausschließlich diese Räume.
- Nachtstrategie nennt die tatsächlich simulierten Räume in Empfehlung und Decision Brain.
- Der Beginn einer Regenphase wird aus der stündlichen Prognose bestimmt; Vorlüften vor Regen wird nur empfohlen, wenn genügend trockene Zeit inklusive Sicherheitsreserve vorhanden ist.
- Nachtprognose trennt `forecast_current_state_ml`, `forecast_closed_windows_ml`, `forecast_without_action_ml` und `forecast_with_strategy_ml`.
- Dashboard und Nachtbenachrichtigung können dadurch „ohne Strategie“ und „mit Strategie“ eindeutig gegenüberstellen.
- Nachtfenster respektieren Minutenwerte aus dem Home-Assistant-Zeitselektor, z. B. 22:30–06:45.
- Wiederaufheizkosten für kontrollierte Nachtlüftung werden nicht berechnet, wenn die Außenluft wärmer als der Raum ist.
- Geräte-, Status-, Manifest- und Frontend-Version sowie Frontend-Cache-Buster auf 0.18.0.4 vereinheitlicht.

Abschlussprüfung: 56/56 automatisierte Tests bestanden; Python-, JavaScript- und JSON-Syntax geprüft.
