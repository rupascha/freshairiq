# FreshAirIQ 0.23.0.10 – Hotfix

## Öffnungsstrategie pro Fenster/Tür

- Bewertet jede konfigurierte Öffnung separat mit ihrer eigenen Referenztemperatur und Referenzfeuchte.
- Nutzt für die Einzelbewertung dasselbe physikalische `evaluate_room`-Modell und dieselbe gelernte Luftwechselrate wie die bestehende Raumlogik.
- Berücksichtigt zusätzlich die Ausrichtung bzw. den vorhandenen Windfaktor je Öffnung.
- Die bestehende Raum-/Hausentscheidung bleibt unverändert: Die neue Ebene entscheidet erst danach, **welche** Öffnung für die bereits beschlossene Lüftung bevorzugt werden soll.
- Bei z. B. zwei Außenfenstern und einer Wintergartentür kann FreshAirIQ gezielt die Außenfenster empfehlen und die Wintergartentür geschlossen lassen.
- Während einer laufenden Lüftung kann eine ungünstige geöffnete lokale Öffnung zum Schließen empfohlen werden, sofern bereits ein sinnvoller Lüftungsweg offen bleibt.
- Eine aktive lokale Fenster-/Türreferenz wird in der 15-Minuten-Bewertung nicht mehr durch die Außenwetter-Prognose ersetzt.
- Ungültige oder unvollständige lokale Referenzpaare werden nicht mit Außenwerten zu einem künstlichen Mischpaar kombiniert.

Der Hotfix verändert keine Lernparameter, Hausgrenzwerte, Prognosemodelle oder kanonischen Raum-/Hausaktionen.
