# FreshAirIQ 0.22.0.0 — Robustness Foundation

Dieses Release ist bewusst ein technisches Härtungsrelease. Die Lüftungsphysik,
Empfehlungslogik und Intelligence-2.0-Entscheidungen werden nicht neu kalibriert.

## Änderungen

- Coordinator-Updates sind jetzt als Fehlerdomäne gekapselt: unerwartete Fehler
  werden als `UpdateFailed` an Home Assistant gemeldet; die letzte gültige
  Coordinator-Ausgabe bleibt erhalten statt einen Kaskadenfehler auszulösen.
- Neuer anonymer Runtime-Robustness-Status mit Update-Erfolgen/-Fehlern,
  Fehlerfolgen, Listener-Anzahl, Event-Coalescing und Wetter-Fetch-Fehlern.
- Persistierte Lernwerte werden gegen `NaN`, `inf`, falsche Datentypen und
  physikalisch unmögliche Kernparameter gehärtet. Gültiges Lernen bleibt erhalten.
- Beschädigte einzelne Raumkonfigurationen können gesunde Räume nicht mehr
  komplett mitreißen. Fehlende Keys werden übersprungen; ungültige Volumen- und
  Sortierwerte degradieren kontrolliert und werden diagnostisch markiert.
- Numerische Optionen erhalten eine zweite defensive Validierung gegen
  beschädigte/hand-editierte HA-Storage-Werte.
- Runtime-Daten werden bevorzugt über `ConfigEntry.runtime_data` bereitgestellt,
  mit einem Kompatibilitätsalias über `hass.data` für ältere HA-/interne Aufrufer.
- Teilweise fehlgeschlagenes Platform-Setup räumt Listener und Runtime-Daten auf,
  damit kein halb geladenes FreshAirIQ zurückbleibt.
- Leere Listener-Sets werden ohne unnötige State-Subscription behandelt.

## Unverändert

- Prognosephysik und Forecast-Gewichtung
- Lernschwellen und Reifestufen
- Recommendation-/Decision-Engine
- Sicherheitsgrenzen
- Dashboard-Funktionen und Nutzerkonfiguration
