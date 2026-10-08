# FreshAirIQ 0.26.4.0

- New Freshy view: the dashboard still offers two views, **Freshy** and **Classic** (card editor → Dashboard view). Existing dashboards keep working: the stored value `iq` now means the Freshy view, `classic` is unchanged.
- Classic is untouched: its markup is byte-identical to 0.26.3.2 in all tested situations (verified in 10 scenarios).
- Freshy view (approved design): a large animated Freshy (150 px) at the top with a short status, a plain-language title built from the affected rooms, one sentence on what to do and a "Warum?" link to the existing decision explanation. Below: a timeline of the next hours (night window, airing window, rain, and only the humidity curves the backend actually forecasts), the slim goal lines, the room list with clear chips (offen / schließen / läuft / prüfen), short facts (mould, moisture, pollen — respecting the card options) and a bottom navigation (Jetzt / Räume / Verlauf / Mehr). "Mehr" opens guests, night, learning, settings and support.
- Freshy has eleven moods, each with its own face and animation: content, wants you to air, airing along (progress ring), goal reached (nod + check), asleep (z z), rain (leaf umbrella), cooling (fanning), mould (worried, sweat drop), sensor missing (question mark), pollen (sneezing), learning (thinking). The mood follows the same situation logic as before. All motion stops under "reduce motion".
- Light and dark Home Assistant themes are both supported.
- Privacy: no fonts or other files are loaded from third-party servers; the view uses Home Assistant's own font.
- Removed the old IQ panel and its compact toggle (replaced by the Freshy view). Four tests that pinned the old Freshy drawing were retired and replaced by `tests/test_feature_0264_freshy_view.py` and a new Playwright test (both views render, Freshy ≥ 140 px, Räume/Verlauf/Mehr open the existing panels). UI contract hashes were re-baselined for this approved change.

## Known limits
- Tested in Chromium (desktop, iPhone/iPad/Android emulation); not yet on a real Home Assistant instance or in Safari/iOS WebKit.
- The design mock-up used the Figtree typeface; it is not bundled. The card uses Home Assistant's font instead so nothing is loaded from external servers.
