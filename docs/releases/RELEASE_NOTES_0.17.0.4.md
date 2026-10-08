# FreshAirIQ v0.17.0.4 – Sensor-Timeout Hotfix

Hotfix ausschließlich für den Fall, dass während einer laufenden Lüftung nicht rechtzeitig zwei neue Luftfeuchte-Sensormessungen eintreffen. Basis ist v0.17.0.3.

## Änderung
- Die 2-Messwerte-Sperre aus v0.17.0.3 bleibt vollständig erhalten.
- Vor Ablauf von 15 Minuten kann bei weniger als zwei neuen Feuchtemessungen weiterhin **keine** Schließentscheidung entstehen.
- Ab 15 Minuten darf FreshAirIQ ersatzweise anhand der bereits vorhandenen physikalischen und gelernten Lüftungslogik entscheiden.
- Ein Timeout allein erzeugt **keine** Schließempfehlung. Geschlossen wird nur, wenn die bestehende Modelllogik einen zu geringen Zusatznutzen, ein erreichtes Ziel, eine ungünstige thermische Effizienz oder die Maximaldauer erkennt.
- Bei Räumen mit direkter Außenreferenz wird zusätzlich die vorhandene 15-Minuten-Wetterprognose geprüft. Wenn der Trocknungsvorteil voraussichtlich verschwindet, darf dies im Timeout-Fall eine Schließempfehlung auslösen.
- Bei eigenen Referenzsensoren (z. B. Wintergarten) wird keine Außenwetterprognose fälschlich auf diese Referenz übertragen.
- Die Begründung kennzeichnet klar, wenn die Entscheidung wegen fehlender Sensordaten modellbasiert erfolgt.

Keine Änderungen an Prognoseberechnung aus v0.17.0.2, Lernmodell, Raumpriorisierung, Pollen-, Schimmel-, Querlüftungs-, Präsenz- oder UI-Logik.
