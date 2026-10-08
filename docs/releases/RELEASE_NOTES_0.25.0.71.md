# FreshAirIQ 0.25.0.71 – Scroll-State & Onboarding Root-Cause Hotfix

- Behebt die Scroll-Rücknavigation strukturell: die Zielposition wird als ausstehender Navigationszustand gesetzt und kann beim Re-Render nicht mehr durch die Scrollposition des gerade verlassenen Fensters überschrieben werden.
- Android/WebView verwendet für Detailinhalte einen eindeutigen nativen Scrollport ohne den bisherigen `height:0`-Flex-Hack und ohne erzwungenes `touch-action` auf allen Kind-Elementen.
- `setup_completed` wird nur noch bei tatsächlich konfigurierten Räumen gesetzt; vorhandene Diagnose-Records allein schließen das Setup nicht mehr fälschlich ab.
- Regressionstests sichern diese drei Fehlerpfade ab.
