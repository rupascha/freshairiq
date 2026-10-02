# FreshAirIQ 0.25.2.21

## Room creation flow hotfix

- Fenster-/Türkontakte bleiben beim Anlegen eines Innenraums optional.
- Ein struktureller Home-Assistant-Reload wird während des mehrstufigen Raumdialogs nicht mehr zwischen Orientierung, Kontaktverzögerung und Referenzdaten ausgelöst.
- Der Reload erfolgt erst nach Abschluss des Kontakt-Workflows; Räume ohne Kontakt schließen den Workflow direkt und gültig ab.
- Regressionstests sichern den kontaktlosen Raum sowie den verzögerten Reload ab.
