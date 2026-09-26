# FreshAirIQ 0.20.2.6 — Prognosevergleich-Hotfix

- friert pro Raum eine Startprognose beim Beginn der Lüftung ein
- vergleicht nur Prognose und Messung mit gleicher Zeitbasis
- verhindert Lernanpassungen aus alten, live überschriebenen oder zeitlich unpassenden Prognosen
- verwendet für den Soll-Ist-Vergleich die prognostizierte Netto-Feuchteänderung
- aggregiert die IQ-Prognosegenauigkeit nur aus wirklich vergleichbaren Sessions
- beseitigt den Widerspruch zwischen Haus-5-Minuten-Kachel und Erklärung: beide nutzen nun denselben signierten Nettoeffekt
- erweitert Diagnosedaten um die Startprognose-Referenz
