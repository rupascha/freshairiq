# FreshAirIQ 0.26.5.2

Bugfix release on top of 0.26.5.1 (community feedback): steadier window messages, no close while a sauna runs, a working automatic exhaust fan, WAQI fine dust and readable small text. Golden master: recommendations unchanged; German and English verified.

## Recommendations
- Never "close" while a moisture source is running (owner report, sauna): for example with several windows open, the house/floor decision closed every open room together – including a room that FreshAirIQ itself was keeping open because a sauna, shower or similar was detected and the reference air was still drier. Such a room is now always taken out of a close ("Keep wellness room open (sauna active)"); if it is the only open room, the close becomes "keep ventilating". The room no longer sends its own close notification either, also with a close threshold below 0.4 g/m³.
- No more contradicting and flapping messages with a single open window: a room with one weak open window could show "Window bedroom keep open · Window bedroom close" and switch between "Keep ventilating", "Close now – the extra benefit is getting small" and "Please close the window" every few minutes. A window that is kept open is no longer also told to close; with only one open window there is nothing to re-route, so the normal close recommendation stays. Two different windows still get a targeted "keep A open · close B".

## Automatic control
- Automatic exhaust fan did not start (community report): switching the fan or cover control on for an existing room only took effect after restarting Home Assistant – it now applies at once, and a fan FreshAirIQ started is switched off when the control is switched off again. A room without its own window contact (typical windowless bathroom) gets the recommendation "ventilate via a connected room"; with "follow the recommendation" its exhaust fan now runs on that recommendation too.

## Room setup (Devices & services)
- Three-state templates that report "geöffnet" (support case, bedroom): "geöffnet" is now read as open, like "offen"/"open". Before, a template with "geöffnet / gekippt / geschlossen" kept a running airing on "tilted" when the window was opened fully, did not recognise a first full opening and could put the learning session into quarantine (FAIQ-OPENING-3STATE-006). Real "unknown"/"unavailable" states keep their protection.
- Outdoor fine dust: the "Outdoor fine dust – PM2.5 sensors" picker now also offers PM2.5 sensors without the PM2.5 device class – sensors in µg/m³ and the sensors of the WAQI integration (e.g. `sensor.<city>_pm25`). Note: WAQI reports an air quality index instead of µg/m³; with WAQI set the PM2.5 limit under Air quality to about 100.

## Dashboard
- Readable small text (community feedback): every small text of the card now follows the text size settings – including the learning pages ("Your home", forecasts, habits, model quality, long-term learning), info pages, labels and hints, which had fixed sizes before. New setting "Learning model & analysis"; all text sizes now go up to 200 % (before 150 %). At 100 % everything looks exactly as before. Dashboard card → Edit → Text sizes for this card.

## Diagnostics
- Diagnostics: for every window/door contact the anonymous diagnostics now show its kind (binary sensor or sensor), its origin (e.g. template, zha, mqtt) and whether it reports three states, plus how many contacts of a room share one display name – still without names or entity IDs. This shows at a glance when one window is configured twice or through a self-built three-state template.
