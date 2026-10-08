# FreshAirIQ 0.25.2.15 — Contact Identity & Passage Door UI Hotfix

The native Home Assistant contact-reference editor now handles one actual window/door contact per page.

The page identifies the opening using the Home Assistant friendly name (with a readable entity-id fallback) instead of generic `opening_1` / `opening_2` fields. Static schema field names allow Home Assistant to render German and English labels and descriptions reliably.

The passage-door option now includes the terrace/balcony smoking example and explicitly requires a genuine three-state contact sensor installed in the door hardware.

Stored per-contact data and Dashboard synchronization remain unchanged.
