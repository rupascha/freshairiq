# FreshAirIQ 0.26.4.4

- Fix (community report, also reported in the dashboard): "Raum hinzufügen", "<Raum> bearbeiten" and "Importierten Raum vervollständigen" showed `Translation [formatjs Error: MISSING_VALUE] … contact_name` at the top. These pages had inherited the text of the per-window page, including placeholders they never receive. They now have their own short description. A new permanent test checks that every placeholder used in a dialog text is supplied by every form of that dialog (de/en) and fails on the old texts.
- "Unknown error occurred" after "Schlafzimmer bearbeiten → OK" (community report): this is the `include_back` NameError of GitHub #12 in the next page (the per-window settings). It is fixed since 0.26.2.13; the reporter's version is older. Since 0.26.4.3 such crashes are additionally recorded as `FAIQ-CONFIG-FLOW-001`.
- Add-room wizard (Devices & services → Raum hinzufügen): every page after the first now has "← Zurück zur vorherigen Seite" (priorities → room data with the entered values kept; window page → previous window or priorities). The separate "Himmelsrichtung" and "Öffnungsverzögerung" pages were removed – the per-window page already asks for both.
- "Raum-Prioritäten" and "Raum auswählen" (central settings) now also offer "← Zurück zur vorherigen Seite" instead of only OK or closing the whole dialog.
- Resident profiles: the field labels now show the resident's name ("Anna – Räume", "Anna – Benachrichtigungsziele") instead of "Erwachsener 1 – …". Unnamed slots keep "Erwachsener N"/"Kind N". Names entered in the same step appear the next time the page is opened.

## Known limits
- Home Assistant has no native back button in config dialogs; the back option is a checkbox followed by OK.
- Tested with unit/static tests; the dialogs were not clicked through in a real Home Assistant.
