# FreshAirIQ 0.20.5.3

Hotfix auf Basis von 0.20.5.2.

## Behoben

- Persönliche Bewohner-Endgeräte funktionieren jetzt auch ohne zusätzlich gesetzte globale Benachrichtigungsziele.
- Raumbezogene Meldungen werden an die dem Raum zugeordneten Bewohner-Endgeräte geroutet; doppelte Zustellung an dasselbe Ziel wird vermieden.
- Nacht-/Hausmeldungen berücksichtigen persönliche Endgeräte ebenfalls.
- Gäste-Schnellsteuerung verwendet stabile `freshairiq_entity_key`-Metadaten und bleibt nach Entity-Umbenennungen funktionsfähig.
- Haustiersichere Präsenzsensoren wirken jetzt auch dann, wenn sie nicht zusätzlich in der allgemeinen Präsenzsensor-Liste stehen.
- Änderungen normaler Einstellungen speichern ohne Neuaufbau des Einstellungsfensters; der Scrollstand bleibt erhalten.
- „Grundlagen“ verwendet ein kompatibles Home-Cog-Icon.
- Gebäude und Bewohner/Anwesenheit sind in getrennte Einstellungsseiten aufgeteilt.
- Bewohnerprofile wurden visuell als besondere persönliche IQ-Profile hervorgehoben.

## Unverändert

Prognosephysik, Lernmodell, Sicherheitsgrenzen, Raumdatenmodell und Dashboard-Hauptdarstellung wurden durch diesen Hotfix nicht verändert.
