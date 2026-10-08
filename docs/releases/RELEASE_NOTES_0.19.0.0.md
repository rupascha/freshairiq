# FreshAirIQ 0.19.0.0

## Neue Feuchtequellen-Intelligenz

- Räume können Dusche, Badewanne und/oder Sauna als mögliche Feuchtequellen hinterlegen.
- Neue adaptive Erkennung arbeitet mit absoluter Feuchte, Raumvolumen, Referenzluft, Temperatur, Fensterzustand und gelerntem Luftwechsel.
- Gemessene Feuchtezunahme wird von der physikalisch erwarteten Lüftungsabfuhr getrennt. Dadurch kann ein Raum trotz steigender Feuchte wirksam gelüftet werden.
- Aktive Feuchtequellen verhindern eine verfrühte Schließempfehlung, solange die Referenzluft trockener und Lüften sinnvoll ist.
- Bei geschlossenen Fenstern kann eine erkannte Feuchtequelle eine gezielte Lüftungsempfehlung auslösen.
- Hysterese schützt vor Flattern bei kurzen Duschpausen bzw. Sauna-Aufgüssen.
- Raumdetail zeigt erkannte Feuchtequelle, Sicherheit und geschätzte Feuchteproduktion.
- Zustand und Kurzzeithistorie überstehen Integration-Reloads/HA-Neustarts.

Die Raumausstattung ist nur ein Kontextsignal. Ohne passende physikalische Messsignatur wird keine Dusche/Sauna/Bad-Aktivität behauptet.
