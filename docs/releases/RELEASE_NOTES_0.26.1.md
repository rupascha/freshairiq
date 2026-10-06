# FreshAirIQ 0.26.1

Cross-platform configuration hotfix based on the verified v0.26.0 public release.

## Fixed
- Central Dashboard multi-select settings no longer rely on native HTML `<select multiple>`, whose interaction differs between desktop browsers and the iOS Home Assistant WebView.
- Existing selections remain explicitly visible as checked items and multiple values can be toggled independently.
- Resident room and personal notification-target selection use the same explicit interaction model.
- The notification test button remains available.

## Scope
No recommendation, learning, ventilation-session, room calculation, notification routing, settings API, or Home Assistant config-flow semantics were changed. Legacy notify services and modern notify entities via `notify.send_message` retain their existing backend contracts.

## Note on service-specific fields
FreshAirIQ continues to call legacy notify services using their existing generic title/message contract. Provider-specific mandatory fields (for example a recipient required by a particular email notify integration) are not invented by this hotfix.
