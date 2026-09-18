# FreshAirIQ 0.24.14.2 Hotfix

- Trustworthy measured ventilation can teach the physical forecast model even when the user did not explicitly follow a recommendation. Slowly reporting `held` frames are learned with reduced weight, and a fresh indoor end-pair is no longer discarded merely because the weather/reference entity reported slowly; objective validation remains strict.
- A short anti-flap floor prevents a reference-source change after closing from reversing a stop/wait decision into a fresh ventilation recommendation after only a few minutes. Urgent mould/CO₂ and strong new moisture-source overrides remain active.
- Covers/shutters are assigned per window/door contact. Legacy single-contact assignments migrate automatically; ambiguous multi-contact legacy assignments remain fallback-only until reassigned.
- Dashboard and Devices & Services rebase and synchronize the same ConfigEntry/room subentries so stale native forms cannot overwrite dashboard settings.
