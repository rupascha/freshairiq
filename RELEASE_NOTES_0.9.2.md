# FreshAirIQ v0.9.2 – Dashboard Status Hotfix

## Behoben

- Dashboard zeigt nicht mehr dauerhaft „FreshAirIQ wartet auf die Status-Entität“.
- Die kanonische Entität `sensor.freshairiq_status` wird wieder sofort als gültige Statusquelle akzeptiert, auch wenn Home Assistant deren Zusatzattribute nach einem Neustart/Reload noch aufbaut.
- Die alternative Statussuche ist toleranter gegenüber teilweise aufgebauten Attributen.
- Frontend-Cache-Busting auf v0.9.2 angehoben, damit Home Assistant/iOS nicht weiter eine alte `freshairiq-card.js` aus dem Cache lädt.

## Unverändert

Die Berechnungs-, Forecast-, Recommendation-, Presence-, Energy-, Coordinator- und Storage-Logik wurde durch diesen Hotfix nicht verändert.
