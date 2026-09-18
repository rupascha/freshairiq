# FreshAirIQ 0.21.0.1 – Stability & Performance Hotfix

- Struktur-Räume ohne Klima-Sensoren sind jetzt vollständig robust und werden niemals von Klima-, Lern- oder Lüftungslogik ausgewertet.
- Native HA-Raumkonfiguration erlaubt bei deaktivierter Klimaberechnung ebenfalls fehlende Temperatur-/Feuchtesensoren.
- Wetter-Forecasts behalten bei transienten Providerfehlern den letzten gültigen Cache und werden zeitnah erneut abgefragt.
- Relevante Sensor-Event-Bursts werden für 120 ms gebündelt, ohne Berechnungslogik oder Aktualität messbar zu verändern.
- Hauswasser-Statistik wird maximal einmal pro Minute beprobt, damit Sensorbursts keine unnötigen Persistenz-Schreibvorgänge erzwingen.
- Diagnostik kompaktierte unveränderte Altdateien nicht mehr stündlich erneut.
- iOS/Safari/WebView-Kompatibilität für Blur-Effekte durch `-webkit-backdrop-filter` verbessert; bestehende Fallbacks bleiben erhalten.
- Keine Physik-, Prognose-, Lern-, Entscheidungs- oder Sicherheitslogik wurde verändert.
