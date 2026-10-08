# FreshAirIQ 0.26.4.5

English Home Assistant installations (and every other non-German language, which Home Assistant shows in English) now get FreshAirIQ fully in English.
- Recommendations, reasons, night strategy, learning status, room explanations and status texts: FreshAirIQ still decides in German internally, but the published coordinator data is translated to English when Home Assistant is not set to German. The learning state and every decision stay identical (verified on all 117 golden-master cycles: same learning state, no German text left; German output unchanged). User names (rooms, floors, residents) are never translated.
- Push notifications follow the Home Assistant language (title and message).
- Ventilation log PDF: English labels, ISO dates and decimal points for English installations; API error messages of the PDF and feedback endpoints are English too.
- Devices & services: diagnostics consent, reporting mode and the area menu now use Home Assistant translations instead of German labels; floor names ("Ground floor", "Unassigned"), operating profile and heating system in dialog texts, "Room"/"No rooms set up yet" fallbacks and resident slots ("Adult 1") are English. Resident slots were German for languages other than English (e.g. French) — now English like the rest of the dialog.
- Repairs: the missing-entity notice names the configuration context in English ("Kitchen: Humidity").
- House status sensor: its states now have translations ("Close windows", "Ventilation running", … / German labels for German installations) instead of raw codes.
- Dashboard (English): over 400 more card texts translated (decision tiles, room overview and room detail, support panel, learning quality, PDF dialog, editor), numbers and dates use English format ("21.8 °C"), "3 people" instead of "3 Personen", room icons also recognise English room names (bedroom, bath, hall, office, guest, nursery, …), and the card recognises the English backend texts where it used German words to pick a state.
- New permanent checks: `tools/coordinator_golden.py --english` (English run must keep the identical learning state and publish no German text) and a test that fails when a new German user-facing text has no English translation.

## Known limits
- Only German and English: every language other than German gets English, like Home Assistant's own fallback.
- If Home Assistant is set to English but a user's profile language is German, the dashboard frame is German while backend texts (recommendations, reasons) arrive in English — the backend has one language per installation.
- Diagnostics exports for the Hub stay German/technical.
- Tested with unit/static tests, the coordinator golden master in German and English and rendered card audits; not tested in a real Home Assistant with English settings.
