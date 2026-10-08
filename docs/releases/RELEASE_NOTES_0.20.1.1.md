# FreshAirIQ 0.20.1.1

Hotfix für das Scrollverhalten des großen Details-Fensters. Während dieses Fenster geöffnet ist, bleibt sein DOM bei Home-Assistant-State-Updates stabil, statt nach einem verzögerten Re-Render neu aufgebaut zu werden. Dadurch wird derselbe bewährte Snapshot-Ansatz verwendet wie in den übrigen langen FreshAirIQ-Detailfenstern. Interaktive Unterfenster bleiben weiterhin live.

Es wurden keine Funktionen, Ansichten, Berechnungen oder Konfigurationswerte geändert.
