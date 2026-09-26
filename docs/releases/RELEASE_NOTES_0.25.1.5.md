# FreshAirIQ 0.25.1.5 – Frontend i18n Architecture Hotfix

## Deutsch / English
- Führt einen stabilen, schlüsselbasierten Frontend-i18n-Katalog mit expliziten deutschen und englischen Texten ein.
- Das neue FreshAirIQ-IQ-Dashboard und die gemeinsame Dashboard-Navigation verwenden ihre Übersetzungen jetzt direkt beim Rendern statt nachträglich sichtbaren DOM-Text umzuschreiben.
- Der bestehende klassische Dashboard-Bestand bleibt kompatibel: seine historische Übersetzungsbrücke wird nur noch auf dem noch nicht migrierten Legacy-Fragment angewendet und zwar bevor dieses in den sichtbaren Shadow DOM eingehängt wird.
- Neue UI-Texte können über stabile Keys mit Variablen und englischem Fallback ergänzt werden.
- Regressionstests sichern Deutsch/Englisch, den neuen IQ-Pfad und die Render-Reihenfolge ab.

## German / English
- Introduces a stable key-based frontend i18n catalog with explicit German and English copy.
- The new FreshAirIQ IQ dashboard and shared dashboard navigation now resolve translations while rendering instead of rewriting visible DOM text afterward.
- The existing classic dashboard remains compatible: its historical translation bridge is limited to the not-yet-migrated legacy fragment and runs before that fragment is mounted into the visible Shadow DOM.
- New UI copy can be added through stable keys with variable interpolation and an English fallback.
- Regression tests protect German/English coverage, the new IQ path and localization-before-mount ordering.

## Scope
- Frontend localization architecture only.
- No changes to ventilation calculations, sensors, learning, diagnostics, room logic, dashboard data sources or mascot state logic.
