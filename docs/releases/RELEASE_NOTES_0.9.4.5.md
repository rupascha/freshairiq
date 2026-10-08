# FreshAirIQ 0.9.4.5 – Stability Hotfix

Reiner Hotfix auf Basis von 0.9.4.4. Keine Änderungen an Berechnungsmodellen, Empfehlungen, Layout oder Funktionsumfang.

## Behoben
- Ein bereits geplanter verzögerter Full-Render wird beim Öffnen bzw. Navigieren in der Raumansicht abgebrochen. Dadurch kann ein alter Timer den stabilen Raum-DOM nicht nachträglich neu aufbauen.
- Die Haus-Empfehlungssignatur wird bei aktivierter Benachrichtigung nicht mehr gespeichert, wenn kein Notify-Service erreichbar war. Dadurch kann die Empfehlung später erneut zugestellt werden.
- `__pycache__`-Ordner und `.pyc`-Dateien werden nicht mehr im Release-Paket ausgeliefert.
