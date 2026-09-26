# FreshAirIQ 0.9.4.4 – Room Browser Scroll Hotfix

Hotfix auf Basis von 0.9.4.3.

## Behoben

- Die Raumübersicht wird während Home-Assistant-State-Updates nicht mehr neu aufgebaut, solange sie geöffnet ist.
- Dadurch bleibt auf iOS/Home-Assistant-WebView derselbe native Scroll-Container bestehen und kann nicht mehr durch einen Shadow-DOM-Neuaufbau auf Position 0 zurückspringen.
- Die Raum-Detailansicht bleibt wie bereits zuvor ebenfalls stabil, solange sie geöffnet ist.

Keine Änderungen an Berechnungslogik, Empfehlungen, Raumdaten, Einstellungen oder Layout.
