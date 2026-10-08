# FreshAirIQ 0.25.2.23

Hotfix für die native Home-Assistant-Raumerstellung unter **Einstellungen → Geräte & Dienste → FreshAirIQ → Raum hinzufügen**.

- Behebt `Unknown error occurred` nach Kontaktverzögerungen: der veraltete Aufruf nicht mehr vorhandener Sammel-Referenzfunktionen wurde auf den bereits verwendeten per-Kontakt-Workflow umgestellt.
- Räume ohne Fenster-/Türkontakt werden weiterhin unterstützt und gelangen direkt in denselben atomaren Abschluss.
- Der native Raumdialog besitzt wieder vollständige deutsche und englische Bezeichnungen, Abschnittstexte und Felderklärungen; `optional_actuators` wird nicht mehr als Rohschlüssel angezeigt.
- Der bestehende atomare Subentry-Commit und die Synchronisation in die kanonischen FreshAirIQ-Raumdaten bleiben unverändert.
