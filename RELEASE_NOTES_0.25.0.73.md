# FreshAirIQ 0.25.0.73

## Unterfenster-Back-Scroll Root-Cause-Hotfix

- Behebt das Zurückspringen an den Anfang beim Wechsel `Details → Unterfenster → zurück` und `Räume → Raum → zurück`.
- Ursache behoben: Beim Zurücknavigieren wurde die bereits gespeicherte Parent-Scrollposition während `_render()` fälschlich mit der Scrollposition des noch im DOM befindlichen Child-Fensters überschrieben.
- Die Parent-Position bleibt jetzt unangetastet und wird nach dem Rendern wieder auf den neuen Scrollcontainer angewendet.
- Android-Touch-Scroll-Hotfix aus 0.25.0.72 bleibt unverändert.
- Keine Änderung an Lüftungs-, Lern-, Diagnose- oder Berechnungslogik.
