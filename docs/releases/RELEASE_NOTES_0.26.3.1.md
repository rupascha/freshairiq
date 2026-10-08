# FreshAirIQ 0.26.3.1

## Privacy fix
In 0.26.3.0 the anonymous activity heartbeat still registered the installation at the diagnostics server on start-up, even if you had not agreed to share diagnostics. From 0.26.3.1 FreshAirIQ makes **no network request to the diagnostics server at all** until an admin agrees.

## Under the hood
The core update cycle (previously one function of about 3,000 lines) is now split into named, separately testable phases. Behaviour is unchanged; this is verified by a new golden-master test that replays six household scenarios cycle by cycle and requires identical results.
