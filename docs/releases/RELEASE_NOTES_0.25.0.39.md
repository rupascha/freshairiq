# FreshAirIQ 0.25.0.39 — Public Diagnostics Endpoint Hotfix

## Fixed / hardened
- Diagnostics uploads now use the public HTTPS endpoint `https://diagnostics.freshairiq.com`.
- Removes the production dependency on the private LAN address `192.168.178.150`.
- Existing diagnostics enrollment, authentication, chunking, retry and privacy opt-in behavior is unchanged.

## Scope
No ventilation, forecast, learning, recommendation, entity, configuration-flow or dashboard logic was changed.
