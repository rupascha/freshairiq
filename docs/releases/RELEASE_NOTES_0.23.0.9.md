# FreshAirIQ 0.23.0.9 – Hotfix

- Referenzsensor-Auswahl im Dashboard akzeptiert jetzt auch gültige Temperatur-/Feuchtesensoren, die nur über °C/°F/K bzw. % gekennzeichnet sind und keine Home-Assistant-`device_class` besitzen.
- Referenztemperatur und Referenzfeuchte können jetzt pro Fenster-/Türkontakt auch in **Geräte & Dienste** konfiguriert werden.
- Kontaktbezogene Referenzen werden ausschließlich als vollständiges Temperatur-/Feuchte-Paar gespeichert; Teilpaare werden abgewiesen.
- Ungespeicherte Werte im Raumeditor bleiben bei Live-Updates erhalten, sodass die Feuchtereferenz beim Auswählen der Temperaturreferenz nicht mehr zurückgesetzt wird.
- Entfernte Kontakte verlieren automatisch veraltete Referenzzuordnungen.
- Keine Änderungen an Prognose-, IQ-, Lern-, Empfehlungs- oder Lüftungsphysik.
