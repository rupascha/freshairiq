# FreshAirIQ 0.26.4.9

User feedback release. Recommendations are unchanged (golden master: all published values identical; only message bookkeeping in the store differs because messages are now also produced when phone notifications are off; German and English verified).

Fix (feedback FAIQ-FB-CA969D3722D2: "nach dem Lernvorgang die Meldung, der Rollo im Schlafzimmer war zu 96 % geschlossen – tatsächlich war er zu 90 % geöffnet"): a single moment with the shutter closed more than the learning limit (default 20 %) blocked the learning sample of the whole airing – typically the seconds after opening the window while the shutter was still on its way up – and the message reported that moment's value. The guard now measures how long the shutter was too far closed during the airing and skips the sample only when that was the case for at least 2 minutes and at least a quarter of the time. Moving shutters (opening/closing) are not judged. The message now says how long: "Rollladen/Jalousie war 10 von 15 Minuten stärker als die Lern-Grenze von 20 % geschlossen (bis zu 96 %)".

Docs (user request HarryP): **two contacts per window**. FreshAirIQ keeps detecting 2-state and 3-state window contacts automatically; there is no extra pairing setting. The README (HACS description) now explains step by step how to combine two 2-state contacts (bottom = open, top = tilted) into one 3-state sensor with a Home Assistant template helper – via the UI or as ready-to-copy YAML template – and to assign only that helper to the room.

New (user request HarryP, Node-RED/Alexa): event **`freshairiq_notification`** – every FreshAirIQ message (room and house recommendations, mould, sensor, airing finished, learning, night strategy) as Home Assistant event with `title`, `message` and a ready-to-speak `speech` text, also when phone notifications are switched off. Documented with Node-RED examples in docs/AUTOMATIONEN.md / AUTOMATIONS.md.

Room view (community feedback "Schrift immer kleiner", "Was bedeutet Oberflächen-RH?"):
- Larger text in the room view: values 15 px instead of 12 px, labels 10.5 px instead of 7.5 px, reasons and hints 11–11.5 px (the card's font-size settings still scale them).
- Every tile in the room view (temperature/humidity, last measurement, potential/balance, next minutes, **surface RH**, balance over days, airings, reheating cost, learning samples, Routine-IQ, Strategie-IQ, feedback, Learning 3.0), the data-quality badge and the "last learning measurement" box now open an explanation window on tap – with the room's current values, in German and English. Small "i" marks show what can be tapped; close with ✕, tapping beside it or Escape. It stays open during live updates.

Devices & services (community feedback Nordlicht-13): every room was listed twice – as a device under "Devices that don't belong to a sub-entry" and again as an empty room sub-entry at the bottom. Room devices now belong to their room sub-entry, so each room appears once, with its device and entities inside. Existing installations are moved once at start-up; entities are moved before their device, so entity IDs, names, history and customisations stay unchanged. Only the central "FreshAirIQ" device remains outside the rooms.

Freshy card (IQ dashboard):
- Fix: in an opened room the goals were squeezed – the first goal (e.g. humidity) became an empty, dashed 18 px strip and the second filled the whole width, partly covering the values below. The goal row inherited the 17 px icon column of the reason lines. Goals now sit side by side in one row of equal width – two or, with CO₂, three goals. The classic dashboard uses its own goal layout and was not affected.
- The three tiles "Nacht / Pollen / Lernen" at the bottom of the Freshy card were removed to keep the card slim. The information stays reachable under Details.

Diagnostics export as ZIP: "Diagnose exportieren" now downloads a ZIP with the unchanged JSON file inside – nothing removed or rounded, about 1/15 of the size (a 19.8 MB export becomes about 1.2 MB). Home Assistant packs it outside the event loop; the browser no longer parses and re-indents tens of MiB. Older frontends without raw API access still get the JSON file.

Quieter, clearer pushes (user feedback):
- "Lüftung läuft · Lüftung weiter beobachten" is no longer pushed – it asks nothing of the user (still available as event `house_continue`).
- Rooms with an exhaust fan: airing and mould messages add "Alternativ den Lüfter einschalten" (house messages name the rooms).
- New tests: `tests/test_user_feedback_026409.py`.

